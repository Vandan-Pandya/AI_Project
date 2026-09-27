# EduMentor AI — Core Backend (9 Essential Endpoints)

FastAPI educational backend powered by **PostgreSQL**, **Bcrypt + JWT Authentication**, and **Google Gemini AI**.

---

## 🚀 Quick Start

### 1. Activate Virtual Environment
```powershell
.\.venv\Scripts\Activate.ps1
```

### 2. Configure Environment (`.env`)
```ini
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/edumentor_db
JWT_SECRET_KEY=your_secret_jwt_key
GEMINI_API_KEY=your_gemini_api_key
```

### 3. Start the Server
```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### 4. Open Interactive API Docs
Go to **[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)** (or `http://127.0.0.1:8000/`, which redirects to `/docs`).

---

## 📋 The 9 Core Working Endpoints

| # | Group | Method | Endpoint | Description |
|---|:---|:---|:---|:---|
| **1** | **Authentication** | `POST` | `/auth/register` | Register new student or teacher account + create profile row |
| **2** | | `POST` | `/auth/login` | Authenticate email & password $\rightarrow$ get JWT token |
| **3** | | `GET` | `/auth/me` | Fetch authenticated user profile and details |
| **4** | **Study Chat** | `POST` | `/chat` | Ask EduMentor academic study & homework questions |
| **5** | **AI Exams** | `POST` | `/exams/generate` | Prompt AI to generate structured quiz questions in JSON |
| **6** | | `POST` | `/exams/` | Save a quiz template to PostgreSQL |
| **7** | | `GET` | `/exams/{exam_id}` | Load quiz questions and rubric |
| **8** | | `POST` | `/exams/{exam_id}/submit` | Submit answers $\rightarrow$ AI auto-grades & returns score card |
| **9** | **System** | `GET` | `/health` | Server and AI model operational health check |

---

## 🗄️ Database Tables (Full Schema Preserved in `database/schema.sql`)
1. **`users`**: Base authentication credentials, email, password hash, role (`student`/`teacher`/`admin`).
2. **`students`**: 1:1 student details (`grade`, `full_name`).
3. **`teachers`**: 1:1 teacher details (`department`, `full_name`).
4. **`classes`**: Teacher-managed classrooms (`class_name`, `academic_year`).
5. **`enrollments`**: Linking students to classes with `UNIQUE(class_id, student_id)`.
6. **`subjects`**: Curriculum subjects.
7. **`exams`**: Quiz templates and AI-generated questions (`JSONB`).
8. **`exam_submissions`**: Student answers, calculated AI score, and diagnostic feedback (`JSONB`).
