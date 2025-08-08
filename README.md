# Mavericks Coding Platform

Welcome to the **Mavericks Coding Platform** – a gamified coding and learning platform with AI-powered agents, leaderboards, dashboards, and hackathon features.

## Live Application

You can access the hosted application here: **[Mavericks Live](https://maverick.selfmade.one/)**

## Features

* **AI-Powered Agents** for personalized learning:

  * ProfileAgent
  * AssessmentAgent
  * RecommenderAgent
  * TrackerAgent
  * HackathonAgent
* **Leaderboards** to track performance.
* **User & Admin Dashboards**.
* **Hackathon Management** – submit projects, track progress, and compete.
* **Fully Responsive UI** with Tailwind CSS + Bootstrap.

## Installation

Follow these steps to set up the project locally:

```bash
# Clone the repository
git clone <repository_url>
cd <project_folder>

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run the server
python manage.py runserver
```

## API Keys Setup

To access AI features, you need to add your API keys in the following files:

* `myproject/settings.py` at **line 193**
* `myapp/views.py` at **line 5941**

## Deployment

We have hosted the application at **[https://maverick.selfmade.one/](https://maverick.selfmade.one/)**. You can also deploy it using services like Render, Railway, or Vercel for backend + frontend hosting.

## Contributing

We welcome contributions! Please fork the repo, make your changes, and submit a pull request.

