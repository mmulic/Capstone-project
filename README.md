# Capstone-project
visual language model project for capstone 2026
# Disaster Assessment Dashboard

**Automated Disaster Damage Assessment from Aerial Imagery**

**Course:** CS 4485  
**Instructor:** Dr. Semih Dinc  
**Team:** Team 10  
**Date:** February 19, 2026

**Team Members:**  
Ahmad Alhreish, Tanzeel Jaffery, Abdulhameed Abdulhameed, Shaheem Jaleel, Ali Ubaid, Muhamed Mulic

---

## 1. System Overview

### a. Solution Overview

This system automates disaster damage assessment using pre- and post-disaster aerial imagery analyzed by **Google Gemini**, a state-of-the-art Vision-Language Model (VLM).

The workflow begins with **data ingestion**, where georeferenced aerial image pairs (before and after a disaster event) are uploaded and stored in **Amazon S3**. Metadata such as GPS coordinates, timestamps, and location identifiers are extracted and indexed in a **PostgreSQL** database.

When inference is triggered, the backend service—built with **Python FastAPI**—retrieves image pairs from S3, constructs structured prompts, and sends them to the **Google Gemini Vision API**. The VLM analyzes visual differences between pre- and post-disaster images, classifying each property into one of four FEMA-aligned damage categories:

* No Damage
* Minor Damage
* Major Damage
* Destroyed

Each prediction includes a confidence score ranging from **0.0 to 1.0**. Results are persisted in the database alongside geospatial coordinates stored in **GeoJSON** format.

The results are visualized through an interactive web dashboard built with **React** and **Leaflet.js**. Users can explore a map with color-coded damage markers, click on individual properties to view detailed assessment cards (including before/after imagery and model output), and apply filters by damage level, geographic area, or date range.

A sidebar chatbot—powered by the Gemini LLM using a **Retrieval-Augmented Generation (RAG)** approach—allows users to ask natural-language questions such as:

* "What is the damage at 123 Main St?"
* "How many properties were destroyed in Zone A?"

An evaluation module compares predictions against **FEMA ground-truth labels**, computing accuracy, precision, recall, and confusion matrices. The entire system is containerized with **Docker** and deployed on **AWS**, with CI/CD automation handled by **GitHub Actions** and monitoring via **CloudWatch**.

---

### b. System Architecture Diagram

![Proposed System Architecture](docs/images/system_architecture.png)

*Figure 1: Proposed System Architecture*

---

## 2. Module Design and Technical Approach

### a. Data Ingestion & Preprocessing

The data ingestion module handles the intake, validation, and storage of pre- and post-disaster aerial imagery provided by the instructor. Each image includes metadata such as GPS coordinates, capture timestamps, and property identifiers.

Upon upload, images are validated for:

* File format integrity (JPEG / PNG / TIFF)
* Resolution consistency
* Completeness of geospatial metadata

A preprocessing pipeline normalizes image dimensions, applies histogram equalization for lighting consistency, and pairs pre/post images by geographic proximity and property ID. Processed images are stored in **Amazon S3**, while metadata is indexed in **PostgreSQL with PostGIS** extensions for efficient spatial queries.

Ingestion can be triggered manually through the dashboard or programmatically via the `POST /API/ingest` endpoint.

---

### b. Damage Prediction Module (VLM)

This module leverages the **Google Gemini Vision API** to analyze paired aerial images and generate structured damage assessments. The model is prompted to:

1. Compare pre- and post-disaster images
2. Identify visible structural changes
3. Classify damage into FEMA-aligned categories

Each prediction includes:

* Damage class
* Confidence score
* Textual rationale explaining observed indicators

The model input is a multi-modal prompt containing base64-encoded images and structured instructions. The output is parsed as JSON. To manage API costs and rate limits, the system supports:

* Batch processing
* Configurable concurrency
* Retry logic with exponential backoff
* Result caching

An evaluation sub-module computes accuracy, precision, recall, F1-score, and confusion matrices against FEMA ground-truth labels.

---

### c. Backend & API Layer

The backend is built with **FastAPI (Python)**, chosen for its async support, automatic OpenAPI documentation, and strong typing via **Pydantic** models.

Key API endpoints include:

* `POST /API/ingest` — Upload and preprocess image pairs
* `POST /API/predict` — Trigger VLM inference
* `GET /API/results` — Retrieve assessment data with filters
* `POST /API/chat` — Query the chatbot interface
* `GET /API/evaluate` — Run evaluation metrics
* `POST /API/auth/login` — JWT-based authentication

The database layer uses **SQLAlchemy ORM** with async sessions. All endpoints are automatically documented via Swagger UI.

---

### d. Web Dashboard Design

The frontend dashboard is built with **React** and **Leaflet.js** for interactive map visualization. Damage assessments are displayed as color-coded markers:

* Green — No Damage
* Yellow — Minor Damage
* Orange — Major Damage
* Red — Destroyed

Clicking a marker opens a detailed property panel showing before/after imagery, damage classification, confidence score, textual rationale, and FEMA ground-truth label (if available).

A filter sidebar allows narrowing results by damage level, confidence threshold, geographic bounding box, and date range. Summary statistics are displayed as dashboard cards above the map.

The UI uses **Axios** for API communication, **React Router** for navigation, and **Tailwind CSS** for responsive styling.

---

### e. Chatbot Module

The chatbot provides a conversational interface powered by **Google Gemini LLM** using a Retrieval-Augmented Generation (RAG) strategy.

When a user submits a query:

1. Relevant records are retrieved from the database using semantic search and PostGIS spatial queries
2. Retrieved data is formatted into a context block
3. The context and user query are sent to Gemini for grounded response generation

The chatbot is designed to only respond based on retrieved system data and explicitly indicate when information is unavailable. Conversation history is maintained for multi-turn interactions.

---

### f. Cloud Deployment Architecture

The system is deployed on **Amazon Web Services (AWS)** using containerized infrastructure:

* **Backend:** Dockerized FastAPI app on ECS (Fargate)
* **Frontend:** React build hosted on S3 and served via CloudFront
* **Database:** PostgreSQL on Amazon RDS with PostGIS
* **Storage:** S3 with versioning and lifecycle policies
* **Secrets:** AWS Secrets Manager

CI/CD is implemented using **GitHub Actions**, automating testing, Docker image builds, ECR pushes, ECS updates, and frontend deployment. Monitoring and alerting are handled through **CloudWatch** and **SNS**.

---

## 3. Assumptions, Risks & Limitations

### Technical Assumptions

1. The dataset contains properly georeferenced pre/post image pairs
2. Google Gemini can reasonably classify structural damage from aerial imagery
3. AWS services are available through university credits or free-tier allocations
4. FEMA ground-truth labels are provided in a structured format

### Potential Risks

1. VLM accuracy limitations on subtle or uncommon damage patterns
2. API rate limits and usage costs
3. Image quality variability (clouds, shadows, resolution mismatches)
4. Scalability challenges under high concurrent dashboard usage

### Known Limitations

1. No model fine-tuning is performed
2. Chatbot responses are limited to retrieved prediction data
3. Real-time streaming analysis is out of scope

---

## 4. Future Improvements

* Fine-tune an open-source VLM on disaster imagery datasets
* Add real-time image streaming support
* Integrate additional contextual data sources (weather, infrastructure, population density)
* Implement role-based access control (RBAC) for multi-agency collaboration
