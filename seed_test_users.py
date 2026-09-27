import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.database import SessionLocal, init_db
from app.core.security import hash_password
from app.models.models import User, Student, Teacher

def seed_users():
    init_db()
    db = SessionLocal()
    try:
        teachers = [
            {"email": "teacher@edumentor.edu", "password": "Password123", "name": "Dr. Sarah Jenkins", "dept": "Physics & Science"},
            {"email": "math.teacher@edumentor.edu", "password": "Password123", "name": "Prof. Rajesh Sharma", "dept": "Mathematics"},
            {"email": "science.teacher@edumentor.edu", "password": "Password123", "name": "Dr. Elena Rostova", "dept": "General Science"}
        ]
        
        students = [
            {"email": "rohan@student.edu", "password": "Password123", "name": "Rohan Sharma", "grade": "Grade 10"},
            {"email": "ananya@student.edu", "password": "Password123", "name": "Ananya Verma", "grade": "Grade 10"},
            {"email": "aarav@student.edu", "password": "Password123", "name": "Aarav Patel", "grade": "Grade 9"}
        ]

        print("--- Seeding Teachers ---")
        for t in teachers:
            user = db.query(User).filter(User.email == t["email"]).first()
            if not user:
                user = User(
                    email=t["email"],
                    password_hash=hash_password(t["password"]),
                    role="teacher",
                    is_active=True
                )
                db.add(user)
                db.flush()
                teacher_prof = Teacher(
                    teacher_id=user.user_id,
                    full_name=t["name"],
                    department=t["dept"]
                )
                db.add(teacher_prof)
                print(f"[CREATED] Teacher: {t['email']}")
            else:
                user.password_hash = hash_password(t["password"])
                if user.teacher_profile:
                    user.teacher_profile.full_name = t["name"]
                    user.teacher_profile.department = t["dept"]
                else:
                    teacher_prof = Teacher(
                        teacher_id=user.user_id,
                        full_name=t["name"],
                        department=t["dept"]
                    )
                    db.add(teacher_prof)
                print(f"[UPDATED] Teacher: {t['email']}")

        print("--- Seeding Students ---")
        for s in students:
            user = db.query(User).filter(User.email == s["email"]).first()
            if not user:
                user = User(
                    email=s["email"],
                    password_hash=hash_password(s["password"]),
                    role="student",
                    is_active=True
                )
                db.add(user)
                db.flush()
                student_prof = Student(
                    student_id=user.user_id,
                    full_name=s["name"],
                    grade=s["grade"]
                )
                db.add(student_prof)
                print(f"[CREATED] Student: {s['email']}")
            else:
                user.password_hash = hash_password(s["password"])
                if user.student_profile:
                    user.student_profile.full_name = s["name"]
                    user.student_profile.grade = s["grade"]
                else:
                    student_prof = Student(
                        student_id=user.user_id,
                        full_name=s["name"],
                        grade=s["grade"]
                    )
                    db.add(student_prof)
                print(f"[UPDATED] Student: {s['email']}")

        db.commit()
        print(">>> SUCCESS: Seeded test credentials in Supabase database!")
    except Exception as e:
        db.rollback()
        print(f"Error during seeding: {e}")
        raise
    finally:
        db.close()

if __name__ == '__main__':
    seed_users()
