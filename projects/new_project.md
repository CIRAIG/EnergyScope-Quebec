# Adding a new project to the EnergyScope-Québec monorepo

## Steps to add a new project

1. **Create a new directory**: Inside the `projects/` folder, create a new directory for your project. Name it descriptively (e.g., `renewable_integration/`).
2. **Add a README**: Inside your new project directory, create a `README.md` file that describes the project's objectives, methodology, and any specific instructions for running the model.
3. **Update the requirements file**: If your project has specific dependencies, update the `requirements.txt` file in the root of the repository to include those dependencies.
4. **Update the main README**: Add an entry for your new project in the main `README.md` file under the "Projects" section. Include a brief description and a link to your project's README.
5. **Add the project to issue templates and CODEOWNERS**: Add your project to the relevant issue templates (e.g., `feature_request.md`, `bug_report.md`) and to the `CODEOWNERS` file to ensure that issues related to your project are properly assigned.