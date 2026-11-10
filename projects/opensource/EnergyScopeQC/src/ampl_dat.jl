"""
    AmplDat

Minimal reader for AMPL `.dat` files, written for the syntax actually used by ES-QC
(not a general AMPL parser). No dependency.

Supported forms
  - comments `# ...` and `/* ... */` (stripped first, never passed on)
  - `data;` / `model;`                       (ignored)
  - `set NAME := a b c;`, `set NAME[i] := ...;`, `set NAME;` (empty)
  - `param NAME := key val ...;`, `param: NAME := ...;`        (1-D list or scalar)
  - `param NAME : c1 c2 ... := row v v ...;`                (2-D table)
  - `param NAME := [A,*,*] : c1 c2 := row v v ... [B,*,*] : ...;` (slices)
  - `let [{dom}] NAME[idx] := expr;`, `fix [{dom}] VAR[idx] := expr;`
  - `for {dom} { ... }` (nestable), domains `v in SET [diff|union|inter SET|{...}]`
  - expressions: numbers, 'strings', `Infinity`, `+ - * /`, parentheses, `param[idx]`, loop variables,
    `sum {dom} expr` (nestable; the operand extends over the following `+` and `-`, as in AMPL)

Any other form raises a `DatSyntaxError` (file:line).

Files are applied in the given order; the last `let`/`param` wins (as in AMPL).
Overwrites between different files are logged in `DataStore.overwrites`.
Sets computed by the `.mod` (e.g. `TECHNOLOGIES`) are provided through `derived`.
"""
module AmplDat

export DataStore, DatSyntaxError, strip_comments, parse_dat, load_dat_files!, load_dat_files,
       getparam, getset, read_param_defaults, read_param_decls, apply_overrides!, load_dat_string!, foreach_domain

struct DatSyntaxError <: Exception
    file::String
    line::Int
    msg::String
end
Base.showerror(io::IO, e::DatSyntaxError) =
    print(io, "DatSyntaxError: ", e.file, ":", e.line, ": ", e.msg)

# ───────────────────────── 1. Comments ─────────────────────────

"""
    strip_comments(text; file) -> String

Replaces `# ...` and `/* ... */` with nothing, keeping line breaks (line numbers
stay exact) and respecting `'...'` / `"..."` strings. An unclosed `/*` raises an error
(it would otherwise swallow the rest of the file).
"""
function strip_comments(text::AbstractString; file::AbstractString="<string>")
    cs = collect(text)
    n = length(cs)
    out = IOBuffer()
    i = 1; line = 1; q = '\0'
    while i <= n
        c = cs[i]
        if c == '\n'
            line += 1; q = '\0'            # a string never spans a line
            write(out, c); i += 1
        elseif q != '\0'
            write(out, c); c == q && (q = '\0'); i += 1
        elseif c == '\'' || c == '"'
            q = c; write(out, c); i += 1
        elseif c == '#'
            while i <= n && cs[i] != '\n'; i += 1; end
        elseif c == '/' && i < n && cs[i+1] == '*'
            start = line; i += 2; closed = false
            while i <= n
                if cs[i] == '*' && i < n && cs[i+1] == '/'
                    i += 2; closed = true; break
                elseif cs[i] == '\n'
                    line += 1; write(out, '\n'); i += 1
                else
                    i += 1
                end
            end
            closed || throw(DatSyntaxError(String(file), start, "unclosed /* comment"))
            write(out, ' ')
        else
            write(out, c); i += 1
        end
    end
    String(take!(out))
end

# ───────────────────────── 2. Atoms and expressions ─────────────────────────

const NUM_FULL = r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$"

"Key/set atom: 'x' or \"x\" → String, integer → Int, decimal → Float64, otherwise bare word → String."
function parse_atom(tok::AbstractString)
    t = strip(tok)
    if length(t) >= 2 && (t[1] == '\'' || t[1] == '"') && t[end] == t[1]
        return String(t[2:end-1])
    elseif occursin(NUM_FULL, t)
        return occursin(r"^[+-]?\d+$", t) ? parse(Int, t) : parse(Float64, t)
    end
    String(t)
end

"Parameter value: number (Float64), `Infinity`, otherwise string. `.` (AMPL missing value) → nothing."
function parse_value(tok::AbstractString)
    t = strip(tok)
    t == "." && return nothing
    t in ("Infinity", "+Infinity") && return Inf
    t == "-Infinity" && return -Inf
    a = parse_atom(t)
    a isa Integer ? Float64(a) : a
end

abstract type Expr end
struct Lit <: Expr; v::Any end
struct Var <: Expr; name::String end
struct Ref <: Expr; name::String; args::Vector{Expr} end
struct Neg <: Expr; a::Expr end
struct Bin <: Expr; op::Char; a::Expr; b::Expr end
"`sum {dom} body`: sum of `body` over the domain (the operand extends over the following `+` and `-`, as in AMPL)."
struct SumE <: Expr; dom::Vector{Tuple{String,Vector{Tuple{Symbol,Any}}}}; body::Expr end

const TOKEN_RE = r"\G\s*(?:(\d+\.?\d*(?:[eE][+-]?\d+)?(?![A-Za-z_0-9.])|\.\d+(?:[eE][+-]?\d+)?(?![A-Za-z_0-9.]))|([A-Za-z_0-9]+)|('[^']*'|\"[^\"]*\")|([-+*/(),\[\]]))"

function tokenize(s::AbstractString, file, line)
    toks = Tuple{Symbol,Any}[]
    pos = 1; n = lastindex(s)
    while pos <= n
        ms = match(r"\G\s*sum\s*(\{)", s, pos)
        if ms !== nothing                      # `sum {domain}`: the domain text becomes a single token
            i0 = ms.offsets[1]; i = i0; depth = 0; q = '\0'; close = 0
            while i <= n
                c = s[i]
                if q != '\0'; c == q && (q = '\0')
                elseif c == '\'' || c == '"'; q = c
                elseif c == '{'; depth += 1
                elseif c == '}'; depth -= 1; depth == 0 && (close = i; break)
                end
                i = nextind(s, i)
            end
            close == 0 && throw(DatSyntaxError(file, line, "unclosed { in the domain of a sum"))
            push!(toks, (:sum, String(s[i0:close])))
            pos = nextind(s, close)
            continue
        end
        m = match(TOKEN_RE, s, pos)
        if m === nothing
            rest = strip(s[pos:end])
            isempty(rest) && break
            hint = occursin(r"[“”‘’]", rest) ? " (typographic quotes: use straight quotes ' or \")" : ""
            throw(DatSyntaxError(file, line, "unreadable expression near '$(first(rest, 30))'" * hint))
        end
        if m.captures[1] !== nothing
            v = m.captures[1]; push!(toks, (:num, occursin(r"^\d+$", v) ? parse(Int, v) : parse(Float64, v)))
        elseif m.captures[2] !== nothing
            push!(toks, (:word, String(m.captures[2])))
        elseif m.captures[3] !== nothing
            push!(toks, (:str, String(m.captures[3][2:end-1])))
        else
            push!(toks, (:op, m.captures[4][1]))
        end
        pos = m.offset + ncodeunits(m.match)
    end
    toks
end

mutable struct TokStream
    t::Vector{Tuple{Symbol,Any}}
    i::Int
    file::String
    line::Int
end
peek(ts) = ts.i <= length(ts.t) ? ts.t[ts.i] : (:eof, nothing)
next!(ts) = (x = peek(ts); ts.i += 1; x)
isop(x, c) = x[1] == :op && x[2] == c
fail(ts, msg) = throw(DatSyntaxError(ts.file, ts.line, msg))

parse_expr_str(s, file, line) = begin
    ts = TokStream(tokenize(s, file, line), 1, file, line)
    e = parse_sum(ts)
    ts.i <= length(ts.t) && fail(ts, "unexpected remainder in expression '$s'" *
                                 (occursin(r"\d,\d", s) ? " (decimal comma: use a decimal point)" : ""))
    e
end

function parse_sum(ts)
    a = parse_prod(ts)
    while (t = peek(ts); isop(t, '+') || isop(t, '-'))
        next!(ts); a = Bin(t[2], a, parse_prod(ts))
    end
    a
end
function parse_prod(ts)
    a = parse_unary(ts)
    while (t = peek(ts); isop(t, '*') || isop(t, '/'))
        next!(ts); a = Bin(t[2], a, parse_unary(ts))
    end
    a
end
function parse_unary(ts)
    if isop(peek(ts), '-'); next!(ts); return Neg(parse_unary(ts)); end
    if isop(peek(ts), '+'); next!(ts); return parse_unary(ts); end
    parse_primary(ts)
end
function parse_primary(ts)
    t = next!(ts)
    if t[1] == :num;  return Lit(t[2])
    elseif t[1] == :str; return Lit(t[2])
    elseif isop(t, '(')
        e = parse_sum(ts); isop(next!(ts), ')') || fail(ts, "missing closing parenthesis"); return e
    elseif t[1] == :sum
        dom = parse_domain(t[2], ts.file, ts.line)
        return SumE(dom, parse_sum(ts))
    elseif t[1] == :word
        if isop(peek(ts), '[')
            next!(ts); args = Expr[parse_sum(ts)]
            while isop(peek(ts), ','); next!(ts); push!(args, parse_sum(ts)); end
            isop(next!(ts), ']') || fail(ts, "missing closing bracket")
            return Ref(t[2], args)
        end
        return Var(t[2])
    end
    fail(ts, "unexpected expression ($(t[1]) $(t[2]))")
end

# ───────────────────────── 3. Data store ─────────────────────────

"""
    DataStore

- `sets`          simple sets                  `NAME => [elements]`
- `isets`         indexed sets                 `NAME => (idx...) => [elements]`
- `params`        parameters (scalar: key `()`)  `NAME => (idx...) => value`
- `fixes`         `fix` statements (to apply to the JuMP model)
- `overwrites`    overwrites of a value set by *another* file
- `derived`       `NAME => f(db)`: sets computed by the `.mod` (e.g. TECHNOLOGIES)
- `defaults`      `NAME => value`: `default` clauses of the `.mod` `param` declarations (see `read_param_defaults`)
- `decls`         `NAME => [index set of each position]`: `param` declarations of the `.mod` files (see `read_param_decls`);
                  used to validate the `let` statements of user files (`load_dat_files!(...; strict=true)`)
"""
mutable struct DataStore
    sets::Dict{String,Vector{Any}}
    isets::Dict{String,Dict{Tuple,Vector{Any}}}
    params::Dict{String,Dict{Tuple,Any}}
    fixes::Vector{NamedTuple{(:var, :key, :value, :file),Tuple{String,Tuple,Any,String}}}
    overwrites::Vector{NamedTuple{(:param, :key, :old, :new, :old_file, :new_file, :changed),
                                  Tuple{String,Tuple,Any,Any,String,String,Bool}}}
    derived::Dict{String,Function}
    defaults::Dict{String,Any}
    provenance::Dict{Tuple{String,Tuple},String}
    constraints::Vector{NamedTuple{(:stmt, :file),Tuple{Any,String}}}
    file::String
    decls::Dict{String,Vector{Union{Nothing,String}}}   # `param` declarations of the .mod files: name => index set of each position
    strict::Bool                                         # validate `let` statements (user files): known parameter, arity, set membership
    setmemo::Dict{String,Union{Nothing,Set{Any}}}        # members of the sets used by the validation (cache)
end
DataStore(; derived=Dict{String,Function}(), defaults=Dict{String,Any}(),
          decls=Dict{String,Vector{Union{Nothing,String}}}()) =
    DataStore(Dict(), Dict(), Dict(), [], [], Dict{String,Function}(derived), Dict{String,Any}(defaults), Dict(), [], "",
              decls, false, Dict())

"Value of a parameter; explicit error if absent."
function getparam(db::DataStore, name::AbstractString, key::Tuple=())
    haskey(db.params, name) && haskey(db.params[name], key) && return db.params[name][key]
    haskey(db.defaults, name) && return db.defaults[name]
    error("parameter $name: no value for key $key (and no `default` in the .mod)")
end

"""
    read_param_defaults(modfiles) -> Dict{String,Any}

Extracts the `default` clauses of the `param NAME {...} ... default V;` declarations in the `.mod` files.
AMPL applies them when an entry is not defined; needed to evaluate some `let`
(e.g. `let c_maint['YEAR_2015',i] := c_maint['YEAR_2020',i]` when 2020 has no value).
"""
function read_param_defaults(files)
    d = Dict{String,Any}()
    for f in files
        for st in split(strip_comments(read(f, String); file=f), ';')
            m = match(r"^\s*param\s+(\w+)[^:]*?default\s+(\S+)\s*$"s, st)
            m === nothing && continue
            v = parse_value(m[2]); v === nothing || (d[String(m[1])] = v)
        end
    end
    d
end

"""
    read_param_decls(modfiles) -> Dict{String,Vector{Union{Nothing,String}}}

Extracts the `param NAME {set1, set2, ...}` declarations of the `.mod` files: for each parameter, the name of the set indexing
each position (`nothing` when the index is not a plain set name, e.g. `PHASE union {"2015_2020"}`). A scalar parameter has no
position. Used to validate the `let` statements of user files.
"""
function read_param_decls(files)
    d = Dict{String,Vector{Union{Nothing,String}}}()
    for f in files
        for st in split(strip_comments(read(f, String); file=f), ';')
            m = match(r"^\s*param\s+(\w+)\s*(.*)$"s, st)
            m === nothing && continue
            rest = lstrip(String(m[2]))
            idx = Union{Nothing,String}[]
            if startswith(rest, "{")
                depth = 0; stop = 0
                for (k, ch) in enumerate(rest)
                    ch == '{' && (depth += 1)
                    ch == '}' && (depth -= 1; depth == 0 && (stop = k; break))
                end
                stop == 0 && continue
                for part in split_top(rest[2:stop-1], ',')
                    mm = match(r"^\s*(?:\w+\s+in\s+)?(\w+)\s*$", part)
                    push!(idx, mm === nothing ? nothing : String(mm[1]))
                end
            end
            d[String(m[1])] = idx
        end
    end
    d
end

# Time sets are not validated: a user file may legitimately mention a year or a phase outside the current run.
const UNCHECKED_SETS = ("YEARS", "YEARS_WND", "YEARS_UP_TO", "PHASE", "PHASE_WND", "PHASE_UP_TO")

function edit_distance(a::AbstractString, b::AbstractString)
    a, b = collect(a), collect(b)
    prev = collect(0:length(b))
    for (i, ca) in enumerate(a)
        cur = [i]
        for (j, cb) in enumerate(b)
            push!(cur, min(prev[j+1] + 1, cur[j] + 1, prev[j] + (ca == cb ? 0 : 1)))
        end
        prev = cur
    end
    prev[end]
end

"` (did you mean 'x'?)` when a candidate is close to `name`, otherwise an empty string."
function suggestion(name, candidates)
    s = string(name)
    best, bestd = nothing, typemax(Int)
    for c in candidates
        d = lowercase(s) == lowercase(string(c)) ? 0 : edit_distance(s, string(c))
        d < bestd && ((best, bestd) = (string(c), d))
    end
    best !== nothing && bestd <= max(2, length(s) ÷ 5) ? " (did you mean '$best'?)" : ""
end

function set_members(db::DataStore, name::String, file, line)
    get!(db.setmemo, name) do
        try
            Set{Any}(getset(db, name, file, line))
        catch e
            e isa DatSyntaxError ? nothing : rethrow()
        end
    end
end

"""
Validation of a `let` of a user file (`db.strict`): the parameter must be declared in a `.mod`, the key must have the right number
of indices, and each index must belong to its set. Otherwise the statement would silently create an entry the model never reads.
"""
function check_let(db::DataStore, name::String, key::Tuple, file, line)
    (db.strict && !isempty(db.decls)) || return
    if !haskey(db.decls, name)
        throw(DatSyntaxError(file, line, "unknown parameter '$name'" * suggestion(name, keys(db.decls))))
    end
    sets = db.decls[name]
    if length(key) != length(sets)
        want = isempty(sets) ? "no index" : join(coalesce.(sets, "?"), ", ")
        throw(DatSyntaxError(file, line, "parameter '$name' expects $(length(sets)) index(es) ($want), got $(length(key))"))
    end
    for (k, s) in zip(key, sets)
        (s === nothing || s in UNCHECKED_SETS) && continue
        members = set_members(db, s, file, line)
        members === nothing && continue
        k in members || throw(DatSyntaxError(file, line,
            "$name: '$k' is not in $s" * suggestion(k, filter(x -> x isa AbstractString, members))))
    end
end

function setparam!(db::DataStore, name, key::Tuple, val)
    val isa Integer && (val = Float64(val))
    d = get!(db.params, name, Dict{Tuple,Any}())
    pk = (name, key)
    if haskey(d, key) && haskey(db.provenance, pk) && db.provenance[pk] != db.file
        old = d[key]
        push!(db.overwrites, (param=name, key=key, old=old, new=val, old_file=db.provenance[pk],
                              new_file=db.file, changed=!(old == val)))
    end
    d[key] = val
    db.provenance[pk] = db.file
    nothing
end

function getset(db::DataStore, name::AbstractString, file, line)
    haskey(db.sets, name) && return db.sets[name]
    if haskey(db.derived, name)
        db.sets[name] = collect(Any, db.derived[name](db))
        return db.sets[name]
    end
    throw(DatSyntaxError(file, line, "unknown set '$name' (set computed by the .mod? " *
                         "provide `derived[\"$name\"]`)"))
end

"Set `name` (simple or derived); usable from `derived` functions to chain them."
getset(db::DataStore, name::AbstractString) = getset(db, name, "<code>", 0)

# ───────────────────────── 4. Statements ─────────────────────────

abstract type Stmt end
struct SetStmt <: Stmt;  name::String; idx::Union{Nothing,Tuple}; items::Vector{Any}; line::Int end
struct ParamStmt <: Stmt; name::String; entries::Vector{Pair{Tuple,Any}}; line::Int end
struct LetStmt <: Stmt
    kind::Symbol; dom::Vector{Tuple{String,Vector{Tuple{Symbol,Any}}}}
    name::String; idx::Vector{Expr}; rhs::Expr; line::Int
end
struct ForStmt <: Stmt
    dom::Vector{Tuple{String,Vector{Tuple{Symbol,Any}}}}; body::Vector{Stmt}; line::Int
end
"`subject to NAME [{dom}] : lhs <op> rhs ;`: linear constraint added by the user (see `DataStore.constraints`)."
struct ConStmt <: Stmt
    name::String; dom::Vector{Tuple{String,Vector{Tuple{Symbol,Any}}}}
    lhs::Expr; op::Symbol; rhs::Expr; line::Int
end

# -- splitting helpers --

"Splits `s` on `sep` outside braces/brackets/parentheses/strings."
function split_top(s::AbstractString, sep::Char)
    parts = String[]; depth = 0; q = '\0'; buf = IOBuffer()
    for c in s
        if q != '\0'
            c == q && (q = '\0'); write(buf, c)
        elseif c == '\'' || c == '"'
            q = c; write(buf, c)
        elseif c in "{[("
            depth += 1; write(buf, c)
        elseif c in "}])"
            depth -= 1; write(buf, c)
        elseif c == sep && depth == 0
            push!(parts, String(take!(buf)))
        else
            write(buf, c)
        end
    end
    push!(parts, String(take!(buf)))
    parts
end

"Domain `{ v in SET, w in SET2 }` → list of (variable, set expression)."
function parse_domain(s::AbstractString, file, line)
    inner = strip(s)
    (startswith(inner, "{") && endswith(inner, "}")) || throw(DatSyntaxError(file, line, "malformed domain: $s"))
    inner = inner[2:end-1]
    out = Tuple{String,Vector{Tuple{Symbol,Any}}}[]
    for part in split_top(inner, ',')
        m = match(r"^\s*([A-Za-z_]\w*)\s+in\s+(.+?)\s*$"s, part)
        m === nothing && throw(DatSyntaxError(file, line, "unsupported domain (`:` condition?): '$(strip(part))'"))
        push!(out, (String(m[1]), parse_setexpr(m[2], file, line)))
    end
    out
end

"Set expression → sequence [(:set,name)|(:lit,[atoms])|(:op,:diff|:union|:inter)]."
function parse_setexpr(s::AbstractString, file, line)
    seq = Tuple{Symbol,Any}[]
    for m in eachmatch(r"\{[^}]*\}|\w+", s)
        w = m.match
        if startswith(w, "{")
            items = [parse_atom(x) for x in split_top(w[2:end-1], ',') if !isempty(strip(x))]
            push!(seq, (:lit, Any[items...]))
        elseif w in ("diff", "union", "inter")
            push!(seq, (:op, Symbol(w)))
        else
            push!(seq, (:set, String(w)))
        end
    end
    (isempty(seq) || length(seq) % 2 == 0) &&
        throw(DatSyntaxError(file, line, "unsupported set expression: '$s'"))
    seq
end

function eval_setexpr(db, seq, file, line)
    get1(t) = t[1] == :set ? getset(db, t[2], file, line) : t[2]
    res = Any[get1(seq[1])...]
    for k in 2:2:length(seq)
        rhs = get1(seq[k+1]); op = seq[k][2]
        res = op == :diff ? filter(x -> !(x in rhs), res) :
              op == :union ? unique!(vcat(res, rhs)) : filter(x -> x in rhs, res)
    end
    res
end

# -- parsing a statement --

function parse_set(s, file, line)
    m = match(r"^set\s+(\w+)\s*(?:\[(.*?)\])?\s*(?::=\s*(.*))?$"s, s)
    m === nothing && throw(DatSyntaxError(file, line, "unsupported set statement: '$(first(s, 60))'"))
    idx = m[2] === nothing ? nothing : Tuple(parse_atom(x) for x in split_top(m[2], ','))
    items = m[3] === nothing ? Any[] : Any[parse_atom(x) for x in split(m[3])]
    SetStmt(String(m[1]), idx, items, line)
end

function table_entries(name, cols::Vector{String}, rows::Vector{String}, prefix, file, line)
    # prefix: list of (Union{Nothing,atom}); the `nothing` entries (stars) are filled with (row, column)
    w = length(cols) + 1
    length(rows) % w == 0 || throw(DatSyntaxError(file, line,
        "table $name: $(length(rows)) values, a multiple of $w expected (1 key + $(length(cols)) columns)"))
    entries = Pair{Tuple,Any}[]
    nstar = count(isnothing, prefix)
    for r in 1:w:length(rows)
        rk = parse_atom(rows[r])
        for (j, c) in enumerate(cols)
            v = parse_value(rows[r+j]); v === nothing && continue
            key = if isempty(prefix)
                (rk, parse_atom(c))
            else
                it = Iterators.Stateful(nstar == 2 ? (rk, parse_atom(c)) : (rk,))
                Tuple(isnothing(p) ? popfirst!(it) : p for p in prefix)
            end
            push!(entries, key => v)
        end
    end
    entries
end

function parse_param(s, file, line)
    # 1) param: NAME := list
    if (m = match(r"^param\s*:\s*(\w+)\s*:=\s*(.*)$"s, s)) !== nothing
        return ParamStmt(String(m[1]), list_entries(m[1], split(m[2]), file, line), line)
    end
    # 2) param NAME := ...
    if (m = match(r"^param\s+(\w+)\s*:=\s*(.*)$"s, s)) !== nothing
        name, body = String(m[1]), String(m[2])
        if startswith(strip(body), "[")
            entries = Pair{Tuple,Any}[]
            ms = collect(eachmatch(r"\[([^\]]*)\]\s*:", body))
            isempty(ms) && throw(DatSyntaxError(file, line, "param $name: malformed slice"))
            for (k, mm) in enumerate(ms)
                stop = k < length(ms) ? ms[k+1].offset - 1 : lastindex(body)
                seg = body[mm.offset+ncodeunits(mm.match):stop]
                parts = split(seg, ":="; limit=2)
                length(parts) == 2 || throw(DatSyntaxError(file, line, "param $name: missing ':=' in a slice"))
                cols = String.(split(parts[1])); rows = String.(split(parts[2]))
                prefix = Any[strip(x) == "*" ? nothing : parse_atom(x) for x in split(mm[1], ',')]
                append!(entries, table_entries(name, cols, rows, prefix, file, line))
            end
            return ParamStmt(name, entries, line)
        end
        return ParamStmt(name, list_entries(name, split(body), file, line), line)
    end
    # 3) param NAME : c1 c2 ... := table
    if (m = match(r"^param\s+(\w+)\s*:\s*(.*?)\s*:=\s*(.*)$"s, s)) !== nothing
        return ParamStmt(String(m[1]),
            table_entries(m[1], String.(split(m[2])), String.(split(m[3])), Any[], file, line), line)
    end
    throw(DatSyntaxError(file, line, "unsupported param statement: '$(first(s, 60))'"))
end

function list_entries(name, toks, file, line)
    n = length(toks)
    n == 1 && return Pair{Tuple,Any}[() => parse_value(toks[1])]
    n % 2 == 0 || throw(DatSyntaxError(file, line, "param $name: 'key value' list of odd length ($n)"))
    entries = Pair{Tuple,Any}[]
    for k in 1:2:n
        v = parse_value(toks[k+1]); v === nothing && continue
        push!(entries, (parse_atom(toks[k]),) => v)
    end
    entries
end

function parse_let(s, file, line)
    m = match(r"^(let|fix)\s*(\{.*\})?\s*([A-Za-z_]\w*)\s*(?:\[(.*)\])?\s*:=\s*(.*)$"s, s)
    m === nothing && throw(DatSyntaxError(file, line, "unsupported let/fix statement: '$(first(s, 70))'"))
    dom = m[2] === nothing ? Tuple{String,Vector{Tuple{Symbol,Any}}}[] : parse_domain(m[2], file, line)
    idx = m[4] === nothing ? Expr[] : Expr[parse_expr_str(x, file, line) for x in split_top(m[4], ',')]
    LetStmt(Symbol(m[1]), dom, String(m[3]), idx, parse_expr_str(m[5], file, line), line)
end

"Splits `lhs <op> rhs` at the first relation operator outside parentheses; a second relation (a <= x <= b) is rejected."
function split_relation(body::AbstractString, file, line)
    cs = collect(body); depth = 0; q = '\0'; found = nothing
    i = 1
    while i <= length(cs)
        c = cs[i]
        if q != '\0'; c == q && (q = '\0')
        elseif c == '\'' || c == '"'; q = c
        elseif c in "([{"; depth += 1
        elseif c in ")]}"; depth -= 1
        elseif depth == 0
            op = nothing; w = 1
            if (c == '<' || c == '>') && i < length(cs) && cs[i+1] == '='; op = c == '<' ? :<= : :>=; w = 2
            elseif c == '=' && !(i > 1 && cs[i-1] in ":<>!"); op = :(==)
            end
            if op !== nothing
                found === nothing || throw(DatSyntaxError(file, line, "double relation (a <= x <= b) not supported: write two constraints"))
                found = (i, w, op); i += w - 1
            end
        end
        i += 1
    end
    found === nothing && throw(DatSyntaxError(file, line, "constraint without relation <=, >= or ="))
    (i0, w, op) = found
    (String(cs[1:i0-1]), op, String(cs[i0+w:end]))
end

function parse_constraint(s, file, line)
    m = match(r"^subject\s+to\s+([A-Za-z_]\w*)\s*(.*)$"s, s)
    m === nothing && throw(DatSyntaxError(file, line, "malformed constraint: '$(first(s, 60))'"))
    name, rest = String(m[1]), strip(String(m[2]))
    dom = Tuple{String,Vector{Tuple{Symbol,Any}}}[]
    if startswith(rest, "{")
        cs = collect(rest); depth = 0; stop = 0
        for (k, ch) in enumerate(cs)
            ch == '{' && (depth += 1)
            ch == '}' && (depth -= 1; depth == 0 && (stop = k; break))
        end
        stop == 0 && throw(DatSyntaxError(file, line, "constraint $name: unclosed brace in the domain"))
        dom = parse_domain(String(cs[1:stop]), file, line)
        rest = strip(String(cs[stop+1:end]))
    end
    startswith(rest, ":") || throw(DatSyntaxError(file, line, "constraint $name: ':' expected before the expression"))
    lhs, op, rhs = split_relation(rest[2:end], file, line)
    ConStmt(name, dom, parse_expr_str(lhs, file, line), op, parse_expr_str(rhs, file, line), line)
end

# -- splitting the text into statements (recursive for `for`) --

function match_brace(cs::Vector{Char}, i, hi, file, lineof)
    depth = 0; q = '\0'
    for k in i:hi
        c = cs[k]
        if q != '\0'; c == q && (q = '\0')
        elseif c == '\'' || c == '"'; q = c
        elseif c == '{'; depth += 1
        elseif c == '}'; depth -= 1; depth == 0 && return k
        end
    end
    throw(DatSyntaxError(file, lineof(i), "unclosed brace {"))
end

function parse_block(cs::Vector{Char}, lo, hi, file, lineof)::Vector{Stmt}
    stmts = Stmt[]
    i = lo
    while true
        while i <= hi && isspace(cs[i]); i += 1; end
        i > hi && break
        line = lineof(i)
        # `for {dom} { body }` (no trailing `;`)
        if i + 3 <= hi && cs[i] == 'f' && cs[i+1] == 'o' && cs[i+2] == 'r' && !(isletter(cs[i+3]) || isdigit(cs[i+3]) || cs[i+3] == '_')
            j = i + 3
            while j <= hi && isspace(cs[j]); j += 1; end
            (j <= hi && cs[j] == '{') || throw(DatSyntaxError(file, line, "for: domain { } expected"))
            je = match_brace(cs, j, hi, file, lineof)
            dom = parse_domain(String(cs[j:je]), file, line)
            k = je + 1
            while k <= hi && isspace(cs[k]); k += 1; end
            (k <= hi && cs[k] == '{') || throw(DatSyntaxError(file, line, "for: body { } expected"))
            ke = match_brace(cs, k, hi, file, lineof)
            push!(stmts, ForStmt(dom, parse_block(cs, k + 1, ke - 1, file, lineof), line))
            i = ke + 1
            if i <= hi && cs[i] == ';'; i += 1; end
            continue
        end
        # simple statement: up to the `;` outside strings
        j = i; q = '\0'
        while j <= hi
            c = cs[j]
            if q != '\0'; c == q && (q = '\0')
            elseif c == '\'' || c == '"'; q = c
            elseif c == ';'; break
            end
            j += 1
        end
        j > hi && throw(DatSyntaxError(file, line, "statement not terminated by ';': '$(first(String(cs[i:hi]), 50))'"))
        s = strip(String(cs[i:j-1]))
        i = j + 1
        isempty(s) && continue
        head = match(r"^\w+", s)
        w = head === nothing ? "" : head.match
        if w in ("data", "model") && s == w; continue
        elseif w == "set";   push!(stmts, parse_set(s, file, line))
        elseif w == "param"; push!(stmts, parse_param(s, file, line))
        elseif w in ("let", "fix"); push!(stmts, parse_let(s, file, line))
        elseif w == "subject"; push!(stmts, parse_constraint(s, file, line))
        else
            throw(DatSyntaxError(file, line, "unsupported statement: '$(first(s, 60))'"))
        end
    end
    stmts
end

"""
    parse_dat(text; file) -> Vector{Stmt}

Text of a `.dat` file → statements (comments removed). Touches no data.
"""
function parse_dat(text::AbstractString; file::AbstractString="<string>")
    startswith(text, '﻿') && (text = text[nextind(text, 1):end])        # UTF-8 byte order mark (some Windows editors)
    clean = strip_comments(text; file)
    cs = collect(clean)
    nl = findall(==('\n'), cs)
    lineof(p) = searchsortedfirst(nl, p) # number of '\n' before p, + 1
    parse_block(cs, 1, length(cs), String(file), lineof)
end

# ───────────────────────── 5. Execution ─────────────────────────

"""
    evaluate(e, env, db, file, line, vars=nothing)

Evaluates an expression. `vars` (optional) gives access to the model variables (`name => JuMP array` or
`name => function`), used for constraints added by the user (`subject to`).
"""
function evaluate(e::Expr, env, db, file, line, vars=nothing)
    if e isa Lit; return e.v
    elseif e isa Var
        haskey(env, e.name) && return env[e.name]
        e.name == "Infinity" && return Inf
        vars !== nothing && haskey(vars, e.name) && return vars[e.name]
        haskey(db.params, e.name) && haskey(db.params[e.name], ()) && return db.params[e.name][()]
        haskey(db.defaults, e.name) && return db.defaults[e.name]
        throw(DatSyntaxError(file, line, "unknown variable or scalar parameter: $(e.name)"))
    elseif e isa Ref
        key = Tuple(evaluate(a, env, db, file, line, vars) for a in e.args)
        if vars !== nothing && haskey(vars, e.name)
            v = vars[e.name]
            try
                return v isa Function ? v(key...) : v[key...]
            catch err
                msg = "variable $(e.name)$(key) not found in the model"
                if !(v isa Function) && applicable(axes, v) && length(axes(v)) == length(key)
                    for (pos, (k, ax)) in enumerate(zip(key, axes(v)))
                        k in ax && continue
                        msg = "variable $(e.name): '$k' is not a valid value for index $pos" *
                              suggestion(k, filter(x -> x isa AbstractString, collect(ax)))
                        break
                    end
                end
                throw(DatSyntaxError(file, line, msg))
            end
        end
        haskey(db.params, e.name) && haskey(db.params[e.name], key) && return db.params[e.name][key]
        haskey(db.defaults, e.name) && return db.defaults[e.name]
        known = vars === nothing ? keys(db.params) : Iterators.flatten((keys(db.params), keys(vars), keys(db.defaults)))
        throw(DatSyntaxError(file, line, vars === nothing ?
            "$(e.name)$(key) read before being defined" :
            "unknown name '$(e.name)': not a model variable, a parameter, or a value defined earlier" * suggestion(e.name, known)))
    elseif e isa Neg; return -evaluate(e.a, env, db, file, line, vars)
    elseif e isa SumE
        acc = 0.0
        iterate_domain(db, e.dom, copy(env), 1, file, line) do env2
            acc = acc + evaluate(e.body, env2, db, file, line, vars)
        end
        return acc
    else
        a = evaluate(e.a, env, db, file, line, vars); b = evaluate(e.b, env, db, file, line, vars)
        e.op == '/' && b isa Real && b == 0 && throw(DatSyntaxError(file, line, "division by zero"))
        return e.op == '+' ? a + b : e.op == '-' ? a - b : e.op == '*' ? a * b : a / b
    end
end

"Iterates over a domain `{v in SET, ...}`, passing the loop environment to `f(env)`."
foreach_domain(f, db::DataStore, dom, file, line) = iterate_domain(f, db, dom, Dict{String,Any}(), 1, file, line)

function iterate_domain(f, db, dom, env, k, file, line)
    if k > length(dom); f(env); return; end
    v, seq = dom[k]
    for x in eval_setexpr(db, seq, file, line)
        env[v] = x
        iterate_domain(f, db, dom, env, k + 1, file, line)
    end
    delete!(env, v)
end

function run!(db::DataStore, st::SetStmt, env, file)
    if st.idx === nothing
        db.sets[st.name] = st.items
    else
        get!(db.isets, st.name, Dict{Tuple,Vector{Any}}())[st.idx] = st.items
    end
end
function run!(db::DataStore, st::ParamStmt, env, file)
    for (k, v) in st.entries; setparam!(db, st.name, k, v); end
end
function run!(db::DataStore, st::LetStmt, env, file)
    iterate_domain(db, st.dom, env, 1, file, st.line) do en
        key = Tuple(evaluate(a, en, db, file, st.line) for a in st.idx)
        val = evaluate(st.rhs, en, db, file, st.line)
        if st.kind == :let
            check_let(db, st.name, key, file, st.line)
            setparam!(db, st.name, key, val)
        else
            push!(db.fixes, (var=st.name, key=key, value=val, file=db.file))
        end
    end
end
run!(db::DataStore, st::ConStmt, env, file) = (push!(db.constraints, (stmt=st, file=file)); nothing)
function run!(db::DataStore, st::ForStmt, env, file)
    iterate_domain(db, st.dom, env, 1, file, st.line) do en
        for s in st.body; run!(db, s, en, file); end
    end
end

"""
    load_dat_files!(db, files; strict=false)

Applies the files in the given order (the last `let`/`param` wins). Overwrites between
different files are logged in `db.overwrites`. With `strict=true` (user files), each `let` is validated against the
`param` declarations of the `.mod` files (known name, number of indices, membership of each index in its set).
"""
function load_dat_files!(db::DataStore, files; strict::Bool=false)
    db.strict = strict
    empty!(db.setmemo)
    try
        for f in files
            db.file = String(f)
            for st in parse_dat(read(f, String); file=f)
                run!(db, st, Dict{String,Any}(), String(f))
            end
        end
    finally
        db.strict = false
    end
    db
end

"Like `load_dat_files!`, but from a text (symbolic name `name` for traceability)."
function load_dat_string!(db::DataStore, text::AbstractString; name::AbstractString="<string>")
    db.file = String(name)
    for st in parse_dat(text; file=name)
        run!(db, st, Dict{String,Any}(), String(name))
    end
    db
end

load_dat_files(files; derived=Dict{String,Function}(), defaults=Dict{String,Any}()) =
    load_dat_files!(DataStore(; derived, defaults), files)

"""
    apply_overrides!(db, overrides)

User overrides, applied AFTER the `.dat` files (without modifying them). `overrides`: `name => v`
  - scalar `v`: scalar parameter, or broadcast to all entries of an indexed parameter (existing entries
    AND `default` clause of the .mod: e.g. `"i_hurdle" => 0.08` for all technologies and years);
  - dictionary `key(tuple) => value`: precise entries, including new ones
    (e.g. `"i_hurdle" => Dict(("YEAR_2030","WIND_ONSHORE") => 0.08)`).
Explicit errors if the parameter is unknown or if the key arity does not match.
Each override is logged in `db.overwrites` (file `<overrides>`).
"""
function apply_overrides!(db::DataStore, overrides)
    db.file = "<overrides>"
    for (name, v) in overrides
        name = String(name)
        existing = get(db.params, name, nothing)
        existing === nothing && !haskey(db.defaults, name) &&
            error("override: parameter '$name' unknown (neither in the .dat files nor in the `default` clauses of the .mod)")
        arity = existing === nothing || isempty(existing) ? nothing : length(first(keys(existing)))
        if v isa AbstractDict
            for (k, val) in v
                key = k isa Tuple ? k : (k,)
                arity !== nothing && length(key) != arity &&
                    error("override $name: key $key of length $(length(key)), $arity indices expected")
                setparam!(db, name, key, val)
            end
        else
            # Scalar: also replaces the `default` clause of the .mod, so that `SDR => 0.03` or `i_hurdle => 0.08`
            # works even when the parameter has no explicit entry in the .dat files (case of i_hurdle in snapshot).
            val = v isa Integer ? Float64(v) : v
            if existing === nothing || isempty(existing) || arity == 0
                old = get(db.defaults, name, nothing)
                push!(db.overwrites, (param=name, key=(), old=old, new=val, old_file="<default of the .mod>",
                                      new_file="<overrides>", changed=!(old == val)))
                db.defaults[name] = val
                existing !== nothing && !isempty(existing) && setparam!(db, name, (), val)
            else
                db.defaults[name] = val
                for key in collect(keys(existing)); setparam!(db, name, key, val); end
            end
        end
    end
    db
end

end # module
