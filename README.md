# OrcaML — End-to-End MLOps Platform

> A 4th-year engineering capstone project built by three Computer Science students over 4 months — from ideation to a live jury presentation.

---

## Table of Contents

1. [Context & Problem](#context--problem)
2. [What We Built](#what-we-built)
3. [Tech Stack](#tech-stack)
4. [How We Built It](#how-we-built-it)
5. [Challenges & Learnings](#challenges--learnings)
6. [How to Use It](#how-to-use-it)

---

## Context & Problem

The modern MLOps lifecycle is fragmented. Data scientists are expected to master a wide range of specialized tools — one for data cleaning, another for training, yet another for deployment — and to constantly switch between them. On top of that, deploying a model to production requires advanced DevOps knowledge that most data scientists simply don't have.

**OrcaML was built to solve both problems at once.**

It is an end-to-end MLOps platform that automates the full ML model creation cycle through a single, easy-to-use pipeline — starting from raw data and finishing with a deployed, production-ready model accessible via API.

---

## What We Built

OrcaML is organized around a pipeline of four major stages:

### 1. Data Upload
The user uploads their raw dataset directly into the platform.

### 2. Data Cleaning
An automated cleaning sub-pipeline of **5 sequential steps** processes the data, handling common issues and preparing it for training — no manual preprocessing required.

### 3. Model Training
The user can train models using:
- **Manual mode** — choose a specific algorithm and configure it
- **Automatic mode** — run multiple algorithms simultaneously and let the platform identify the best-performing one across multiple metrics

Once training is complete, the user can use the model immediately for predictions, or download the `.pkl` file for use elsewhere.

### 4. Model Deployment
With one click, the trained model is packaged as an **isolated container** and deployed to the cloud. The user receives:
- A unique URL to access the deployed model
- A dedicated **Swagger interface** with three ready-to-use endpoints
- A health monitoring view (real-time logs)

The deployed model can be integrated directly into external projects as an API.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI |
| Frontend | Next.js |
| Relational Database | PostgreSQL |
| Object Storage | Cloudflare R2 |
| Model Metrics | MLflow |
| Model Deployment | Docker SDK (Python) |
| Async Tasks (cleaning & training) | Redis + Celery |
| CI/CD | GitHub Actions |
| Cloud Infrastructure | AWS EC2 |

---

## How We Built It

### Team & Organization

The project was divided into three main workstreams, each owned by a team member:

- **Data Upload & Cleaning**
- **Model Training**
- **Model Deployment**

We worked with the **GitHub Flow** branching strategy to minimize merge conflicts and maintain a clean codebase. Weekly meetings, shared planning sessions, and regular code reviews kept the team aligned throughout the four months.

### Design & Conception

Before writing a single line of code, we went through a full conception phase:

- **Class diagrams** to map the application's data model
- **Use case diagrams** to define what the platform does from the user's perspective
- **Sequence diagrams** to plan the interactions between components

This upfront investment was key to building a solid architecture that matched exactly what we envisioned.

### Engineering Philosophy

We deliberately chose to **over-engineer** certain parts of the project for learning purposes — dynamic containerization, async task pipelines with Redis and Celery, and a full CI/CD pipeline. The goal was to simulate a real professional environment as closely as possible.

---

## Challenges & Learnings

### Designing the Pipeline

The core idea — a unified pipeline from raw data to deployed model — was novel for us. Figuring out where each feature should live in the pipeline, how the stages should connect, and what the user experience should feel like at each step was the most challenging and time-consuming part of the project. Getting this right early was essential; it defined everything that followed.

### Working as a Team

We treated this project like a professional environment:
- Weekly syncs and async communication for decisions
- GitHub Flow to keep feature branches clean
- Shared ownership of architecture decisions

This gave us a real taste of collaborative software development beyond academic exercises.

### Technical Learnings

By pushing the scope deliberately, we gained hands-on experience with:
- Async task management (Redis + Celery)
- Dynamic container creation and lifecycle management via the Docker SDK
- Full-stack development across backend, frontend, and infrastructure
- Setting up a CI/CD pipeline with GitHub Actions

---

## How to Use It

1. **Create an account** on the platform
2. **Create a project** — a project is the top-level container for your work
3. **Add an environment** to your project — each environment holds one dataset and can have multiple trained models
4. **Upload your data**
5. **Clean your data** using the automated cleaning pipeline
6. **Train your model**
   - Use *Manual* mode to pick and configure a specific algorithm
   - Use *Automatic* mode to benchmark multiple algorithms and let OrcaML select the best one
7. *(Optional)* **Download the `.pkl` model file** for external use
8. **Deploy your model** — OrcaML packages it as an isolated container and gives you a live URL
9. **Use your model** — through the Swagger interface or directly as an API in your own project; monitor its health via the logs view

---

*Built with curiosity, late nights, and a shared belief that ML tooling can be simpler.*
