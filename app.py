import os
import sqlite3
import hashlib
import random
from datetime import date, datetime, time, timedelta

import pandas as pd
import streamlit as st


DB_NAME = "academy.db"
UPLOAD_DIR = "uploads"

st.markdown(
    """
    <style>
    /* 화면이 좁을 때 버튼 폰트/패딩 줄이기 (대략 태블릿 이하) */
    @media (max-width: 900px) {
        .stButton button {
            font-size: 0.85rem !important;
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ===== 사이드바 폭 확장 CSS =====
sidebar_width_css = """
    <style>
        [data-testid="stSidebar"] {
            width: 320px !important;
            min-width: 320px !important;
        }
        /* 사이드바 내부 텍스트가 억지로 줄바꿈되지 않도록 */
        [data-testid="stSidebar"] * {
            white-space: nowrap;
        }
    </style>
"""
st.markdown(sidebar_width_css, unsafe_allow_html=True)

# ============== 공통: DB & 유틸 ==============

def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    # 사용자 (마스터/관리자/학생)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,              -- 'master', 'admin', 'student'
            is_approved INTEGER NOT NULL,    -- 0 or 1 (admin만 승인 필요)
            student_id INTEGER,              -- 학생 계정일 때 연결
            is_active INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
        """
    )

    # 학생 기본정보
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            school TEXT,
            grade TEXT,
            parent_phone TEXT,
            memo TEXT
        )
        """
    )

    # 반(클래스)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            level TEXT,
            memo TEXT
        )
        """
    )

    # 반-학생 매핑 (여러 반 가능)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS class_students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            FOREIGN KEY (class_id) REFERENCES classes(id),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
        """
    )

    # 학교 성적
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS school_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            subject TEXT NOT NULL,
            exam_name TEXT,
            score REAL,
            max_score REAL,
            memo TEXT,
            recorded_by INTEGER,
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (recorded_by) REFERENCES users(id)
        )
        """
    )

    # 학원 진도
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS academy_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            class_id INTEGER,
            date TEXT NOT NULL,
            subject TEXT NOT NULL,
            unit TEXT,
            memo TEXT,
            recorded_by INTEGER,
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (class_id) REFERENCES classes(id),
            FOREIGN KEY (recorded_by) REFERENCES users(id)
        )
        """
    )

    # 학원 성적
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS academy_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            class_id INTEGER,
            date TEXT NOT NULL,
            subject TEXT NOT NULL,
            test_name TEXT,
            score REAL,
            max_score REAL,
            memo TEXT,
            recorded_by INTEGER,
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (class_id) REFERENCES classes(id),
            FOREIGN KEY (recorded_by) REFERENCES users(id)
        )
        """
    )

    # 시간표 (요일 기반, 주간 반복)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS timetables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id INTEGER NOT NULL,
            weekday INTEGER NOT NULL,        -- 0=월, 6=일
            start_time TEXT NOT NULL,        -- "HH:MM"
            end_time TEXT NOT NULL,
            subject TEXT NOT NULL,
            room TEXT,
            teacher_name TEXT,
            memo TEXT,
            FOREIGN KEY (class_id) REFERENCES classes(id)
        )
        """
    )

      # 출석 테이블
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            class_id INTEGER,
            date TEXT NOT NULL,
            status TEXT NOT NULL,            -- 정상출석 / 지각 / 미인정결석
            homework_status TEXT,            -- 과제: '○' / '△' / 'X'
            daily_test_status TEXT,          -- 일일테스트: '○' / '△' / 'X'
            checkin_time TEXT NOT NULL,      -- "HH:MM:SS"
            via TEXT NOT NULL,               -- "QR" / "수동"
            recorded_by INTEGER,
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (class_id) REFERENCES classes(id),
            FOREIGN KEY (recorded_by) REFERENCES users(id)
        )
        """
    )


    # 공지 테이블
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS notices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            pinned INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            created_by INTEGER,
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
        """
    )

    # 단어장 세트
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS vocab_sets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            level TEXT,
            created_by INTEGER,
            created_at TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
        """
    )

    # 단어장 내 단어 아이템
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS vocab_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            set_id INTEGER NOT NULL,
            word TEXT NOT NULL,
            meaning TEXT NOT NULL,
            part_of_speech TEXT,
            example_en TEXT,
            example_ko TEXT,
            tags TEXT,
            difficulty INTEGER,
            FOREIGN KEY (set_id) REFERENCES vocab_sets(id)
        )
        """
    )

    # 단어장 할당 (반 / 학생)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS vocab_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            set_id INTEGER NOT NULL,
            class_id INTEGER,
            student_id INTEGER,
            assigned_by INTEGER,
            assigned_at TEXT,
            FOREIGN KEY (set_id) REFERENCES vocab_sets(id),
            FOREIGN KEY (class_id) REFERENCES classes(id),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (assigned_by) REFERENCES users(id)
        )
        """
    )

    # 단어장 퀴즈 결과
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS vocab_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            set_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            taken_at TEXT NOT NULL,
            mode TEXT,
            correct_count INTEGER,
            total_count INTEGER,
            percent REAL,
            FOREIGN KEY (set_id) REFERENCES vocab_sets(id),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
        """
    )

    # 설정 저장용 (예: 마지막 학년 승급 연도)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """
    )

    # 시험지 / 자료 파일
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS exam_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            subject TEXT,
            exam_type TEXT,
            exam_name TEXT,
            exam_date TEXT,
            tags TEXT,
            memo TEXT,
            file_path TEXT NOT NULL,
            original_name TEXT,
            uploaded_by INTEGER,
            uploaded_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (uploaded_by) REFERENCES users(id)
        )
        """
    )

    conn.commit()

    # 마스터 계정 없으면 생성
    cur.execute("SELECT id FROM users WHERE role='master'")
    row = cur.fetchone()
    if row is None:
        cur.execute(
            """
            INSERT INTO users
            (username, password_hash, role, is_approved, student_id, is_active)
            VALUES (?, ?, 'master', 1, NULL, 1)
            """,
            ("master", hash_password("master1234")),
        )
        conn.commit()

    conn.close()


# ============== 인증 / 유저 ==============

def create_admin(username: str, password: str) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO users
            (username, password_hash, role, is_approved, student_id, is_active)
            VALUES (?, ?, 'admin', 0, NULL, 1)
            """,
            (username, hash_password(password)),
        )
        conn.commit()
        ok = True
    except sqlite3.IntegrityError:
        ok = False
    finally:
        conn.close()
    return ok


def create_student_user(student_id: int, username: str, password: str) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO users
            (username, password_hash, role, is_approved, student_id, is_active)
            VALUES (?, ?, 'student', 0, ?, 1)   -- 🔴 1 → 0
            """,
            (username, hash_password(password), student_id),
        )
        conn.commit()
        ok = True
    except sqlite3.IntegrityError:
        ok = False
    finally:
        conn.close()
    return ok


def login_user(username: str, password: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, password_hash, role, is_approved, student_id, is_active
        FROM users
        WHERE username=?
        """,
        (username,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    uid, pw_hash, role, is_approved, student_id, is_active = row
    if pw_hash != hash_password(password):
        return None
    return {
        "id": uid,
        "username": username,
        "role": role,
        "is_approved": bool(is_approved),
        "student_id": student_id,
        "is_active": bool(is_active),
    }


def get_waiting_admins():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, username
        FROM users
        WHERE role='admin' AND is_approved=0
        """
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def approve_admin(user_id: int, approve: bool):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET is_approved=? WHERE id=?",
        (1 if approve else 0, user_id),
    )
    conn.commit()
    conn.close()


def set_user_active(user_id: int, active: bool):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET is_active=? WHERE id=?",
        (1 if active else 0, user_id),
    )
    conn.commit()
    conn.close()


# ============== 학생 / 반 / 시간표 ==============

# ============== 학년 자동 승급 관련 ==============

def _promote_grade_one_step(grade: str) -> str:
    """
    '초1'~'초6', '중1'~'중3', '고1'~'고3' 형태만 승급.
    그 외 형식은 그대로 둔다.
    초6 -> 중1, 중3 -> 고1, 고3 -> 졸업
    """
    if not grade:
        return grade
    grade = grade.strip()
    if len(grade) < 2:
        return grade

    prefix = grade[0]
    num_part = grade[1]

    # 숫자가 아니면 건들지 않음
    if not num_part.isdigit():
        return grade

    n = int(num_part)

    if prefix == "초":
        if 1 <= n <= 5:
            return f"초{n+1}"
        elif n == 6:
            return "중1"
        else:
            return grade
    elif prefix == "중":
        if 1 <= n <= 2:
            return f"중{n+1}"
        elif n == 3:
            return "고1"
        else:
            return grade
    elif prefix == "고":
        if 1 <= n <= 2:
            return f"고{n+1}"
        elif n == 3:
            return "졸업"
        else:
            return grade
    else:
        # 초/중/고 아닌 형식은 건들지 않음
        return grade


def promote_all_students_if_needed():
    """
    매년 한 번만 전체 학생 학년 자동 승급.
    - settings 테이블의 'last_grade_promotion_year' 값을 보고
      현재 연도보다 작을 때만 승급 수행.
    - 처음 실행할 때는 '현재 연도'로 초기화만 하고 승급은 안 함.
    """
    conn = get_connection()
    cur = conn.cursor()

    current_year = datetime.now().year

    # settings 테이블에 기록이 있는지 확인
    cur.execute(
        "SELECT value FROM settings WHERE key='last_grade_promotion_year'"
    )
    row = cur.fetchone()

    if row is None:
        # 처음 사용하는 해에는 승급하지 않고 기준 연도만 기록
        cur.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?)",
            ("last_grade_promotion_year", str(current_year)),
        )
        conn.commit()
        conn.close()
        return

    try:
        last_year = int(row[0])
    except ValueError:
        last_year = current_year

    # 이미 올해 승급했다면 아무 것도 안 함
    if current_year <= last_year:
        conn.close()
        return

    # 여기까지 왔으면 "새해가 되었는데 아직 승급 안 함" → 전체 승급 수행
    cur.execute("SELECT id, grade FROM students")
    rows = cur.fetchall()

    for sid, grade in rows:
        new_grade = _promote_grade_one_step(grade or "")
        if new_grade != (grade or ""):
            cur.execute(
                "UPDATE students SET grade=? WHERE id=?",
                (new_grade, sid),
            )

    # 승급 완료 후 연도 갱신
    cur.execute(
        "UPDATE settings SET value=? WHERE key='last_grade_promotion_year'",
        (str(current_year),),
    )
    conn.commit()
    conn.close()


def add_student(name, school, grade, parent_phone, memo):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO students (name, school, grade, parent_phone, memo)
        VALUES (?, ?, ?, ?, ?)
        """,
        (name, school, grade, parent_phone, memo),
    )
    conn.commit()
    conn.close()


def get_students():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, name, school, grade, parent_phone, memo
        FROM students
        ORDER BY name
        """
    )
    rows = cur.fetchall()
    conn.close()
    return rows

def update_student(student_id, name, school, grade, parent_phone, memo):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE students
        SET name=?, school=?, grade=?, parent_phone=?, memo=?
        WHERE id=?
        """,
        (name, school, grade, parent_phone, memo, student_id),
    )
    conn.commit()
    conn.close()


def delete_student(student_id):
    conn = get_connection()
    cur = conn.cursor()
    # 주의: 연결된 출석/성적 기록은 그대로 남는다 (필요하면 나중에 정리).
    cur.execute("DELETE FROM students WHERE id=?", (student_id,))
    conn.commit()
    conn.close()


def add_class(name, level, memo):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO classes (name, level, memo)
        VALUES (?, ?, ?)
        """,
        (name, level, memo),
    )
    conn.commit()
    conn.close()


def get_classes():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, name, level, memo
        FROM classes
        ORDER BY name
        """
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def assign_student_to_class(student_id, class_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO class_students (class_id, student_id)
        VALUES (?, ?)
        """,
        (class_id, student_id),
    )
    conn.commit()
    conn.close()

def update_class(class_id, name, level, memo):
    """반 정보 수정"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE classes
        SET name = ?, level = ?, memo = ?
        WHERE id = ?
        """,
        (name, level, memo, class_id),
    )
    conn.commit()
    conn.close()


def delete_class(class_id):
    """반 삭제 + 관련 매핑/시간표/성적/출석/단어장 연결 정리"""
    conn = get_connection()
    cur = conn.cursor()

    # 이 반에 연결된 데이터 정리 (필요하면 더 추가 가능)
    cur.execute("DELETE FROM class_students WHERE class_id=?", (class_id,))
    cur.execute("DELETE FROM timetables WHERE class_id=?", (class_id,))
    cur.execute("DELETE FROM academy_progress WHERE class_id=?", (class_id,))
    cur.execute("DELETE FROM academy_scores WHERE class_id=?", (class_id,))
    cur.execute("DELETE FROM vocab_assignments WHERE class_id=?", (class_id,))
    cur.execute("DELETE FROM attendance WHERE class_id=?", (class_id,))

    # 마지막으로 반 자체 삭제
    cur.execute("DELETE FROM classes WHERE id=?", (class_id,))

    conn.commit()
    conn.close()


def get_classes_for_student(student_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT c.id, c.name, c.level
        FROM class_students cs
        JOIN classes c ON cs.class_id=c.id
        WHERE cs.student_id=?
        """,
        (student_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def add_timetable(class_id, weekday, start_time_str, end_time_str,
                  subject, room, teacher_name, memo):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO timetables
        (class_id, weekday, start_time, end_time, subject, room, teacher_name, memo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (class_id, weekday, start_time_str, end_time_str,
         subject, room, teacher_name, memo),
    )
    conn.commit()
    conn.close()


def get_timetables_for_classes(class_ids):
    if not class_ids:
        return []
    conn = get_connection()
    cur = conn.cursor()
    placeholders = ",".join(["?"] * len(class_ids))
    query = f"""
        SELECT t.id, c.name, t.weekday, t.start_time, t.end_time,
               t.subject, t.room, t.teacher_name, t.memo, t.class_id
        FROM timetables t
        JOIN classes c ON t.class_id=c.id
        WHERE t.class_id IN ({placeholders})
        ORDER BY t.weekday, t.start_time
    """
    cur.execute(query, class_ids)
    rows = cur.fetchall()
    conn.close()
    return rows


# ============== 출석 / 공지 ==============

def add_attendance(
    student_id,
    class_id,
    status,
    homework_status,
    daily_test_status,
    via,
    recorded_by,
    date_str=None,   # ← 추가: 선택 날짜
):
    """
    status: '정상출석' / '지각' / '미인정결석'
    homework_status, daily_test_status: '○' / '△' / 'X'
    date_str: 'YYYY-MM-DD' 형식. None이면 오늘 날짜로 처리.
    """
    now = datetime.now()
    if date_str is None:
        date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO attendance
        (student_id, class_id, date, status,
         homework_status, daily_test_status,
         checkin_time, via, recorded_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            student_id,
            class_id,
            date_str,
            status,
            homework_status,
            daily_test_status,
            time_str,
            via,
            recorded_by,
        ),
    )
    conn.commit()
    conn.close()


def get_attendance_records(date_str, class_id=None):
    conn = get_connection()
    cur = conn.cursor()
    query = """
        SELECT a.id,
               a.date,
               a.checkin_time,
               a.status,
               a.homework_status,
               a.daily_test_status,
               a.via,
               s.name,
               s.school,
               s.grade,
               c.name
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        LEFT JOIN classes c ON a.class_id = c.id
        WHERE a.date=?
    """
    params = [date_str]
    if class_id:
        query += " AND a.class_id=?"
        params.append(class_id)
    query += " ORDER BY a.checkin_time DESC"
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return rows

def get_attendance_for_student_month(student_id: int, year: int, month: int):
    """
    특정 학생의 지정 월 출결/과제/일일테스트 기록 반환
    (date, status, homework_status, daily_test_status)
    """
    import calendar

    from datetime import date as _date

    first_day = _date(year, month, 1)
    last_day_num = calendar.monthrange(year, month)[1]
    start_str = f"{year:04d}-{month:02d}-01"
    end_str = f"{year:04d}-{month:02d}-{last_day_num:02d}"

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT date, status, homework_status, daily_test_status
        FROM attendance
        WHERE student_id=? AND date BETWEEN ? AND ?
        ORDER BY date
        """,
        (student_id, start_str, end_str),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_recent_attendance_for_student(student_id: int, limit: int = 20):
    """지정 학생의 최근 출결/과제/일일테스트 기록"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT a.date, a.checkin_time, a.status,
               a.homework_status, a.daily_test_status,
               c.name
        FROM attendance a
        LEFT JOIN classes c ON a.class_id = c.id
        WHERE a.student_id=?
        ORDER BY a.date DESC, a.checkin_time DESC
        LIMIT ?
        """,
        (student_id, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def add_notice(title, content, pinned, created_by):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO notices
        (title, content, pinned, created_at, created_by)
        VALUES (?, ?, ?, ?, ?)
        """,
        (title, content, 1 if pinned else 0, datetime.now().isoformat(), created_by),
    )
    conn.commit()
    conn.close()


def get_notices():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, title, content, pinned, created_at
        FROM notices
        ORDER BY pinned DESC, created_at DESC
        """
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def delete_notice(notice_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM notices WHERE id=?", (notice_id,))
    conn.commit()
    conn.close()


# ============== 성적 / 진도 ==============

def get_common_subjects():
    """
    자주 사용하는 과목 목록.
    나중에 DB나 설정으로 빼고 싶으면 여기만 수정하면 됨.
    """
    return ["국어", "수학", "영어", "사회", "과학"]

def add_school_score(student_id, date_str, subject, exam_name,
                     score, max_score, memo, recorded_by):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO school_scores
        (student_id, date, subject, exam_name, score, max_score, memo, recorded_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (student_id, date_str, subject, exam_name,
         score, max_score, memo, recorded_by),
    )
    conn.commit()
    conn.close()


def add_academy_progress(student_id, class_id, date_str,
                         subject, unit, memo, recorded_by):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO academy_progress
        (student_id, class_id, date, subject, unit, memo, recorded_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (student_id, class_id, date_str, subject, unit, memo, recorded_by),
    )
    conn.commit()
    conn.close()


def add_academy_score(student_id, class_id, date_str, subject,
                      test_name, score, max_score, memo, recorded_by):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO academy_scores
        (student_id, class_id, date, subject, test_name,
         score, max_score, memo, recorded_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (student_id, class_id, date_str, subject, test_name,
         score, max_score, memo, recorded_by),
    )
    conn.commit()
    conn.close()


def get_scores_for_student(table_name, student_id, subject=None):
    conn = get_connection()
    cur = conn.cursor()

    if table_name == "school_scores":
        name_col = "exam_name"
    else:
        name_col = "test_name"

    query = f"""
        SELECT date, subject,
               {name_col},
               score, max_score
        FROM {table_name}
        WHERE student_id=?
    """
    params = [student_id]
    if subject:
        query += " AND subject=?"
        params.append(subject)
    query += " ORDER BY date"

    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return rows

def get_common_subjects():
    """
    자주 사용하는 과목 목록을 리턴.
    나중에 settings 테이블이나 config에서 불러오도록 개선 가능.
    """
    return ["국어", "수학", "영어", "사회", "과학"]


    conn = get_connection()
    cur = conn.cursor()
    subjects = set()

    for tbl in ["school_scores", "academy_scores", "academy_progress"]:
        try:
            cur.execute(
                f"SELECT DISTINCT subject FROM {tbl} "
                "WHERE subject IS NOT NULL AND subject <> ''"
            )
            for (s,) in cur.fetchall():
                subjects.add(s.strip())
        except sqlite3.OperationalError:
            # 테이블 없을 경우 대비
            continue

    conn.close()
    return sorted([s for s in subjects if s])


# ============== 단어장 DB 함수 ==============

def create_vocab_set(name, description, level, created_by):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO vocab_sets
        (name, description, level, created_by, created_at, is_active)
        VALUES (?, ?, ?, ?, ?, 1)
        """,
        (name, description, level, created_by, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_vocab_sets(active_only=True):
    conn = get_connection()
    cur = conn.cursor()
    query = """
        SELECT id, name, description, level, created_by, created_at, is_active
        FROM vocab_sets
    """
    if active_only:
        query += " WHERE is_active=1"
    query += " ORDER BY created_at DESC"
    cur.execute(query)
    rows = cur.fetchall()
    conn.close()
    return rows


def add_vocab_item(set_id, word, meaning, part_of_speech,
                   example_en, example_ko, tags, difficulty):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO vocab_items
        (set_id, word, meaning, part_of_speech, example_en,
         example_ko, tags, difficulty)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (set_id, word, meaning, part_of_speech,
         example_en, example_ko, tags, difficulty),
    )
    conn.commit()
    conn.close()


def get_vocab_items(set_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, word, meaning, part_of_speech,
               example_en, example_ko, tags, difficulty
        FROM vocab_items
        WHERE set_id=?
        ORDER BY id
        """,
        (set_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def assign_vocab_to_class(set_id, class_id, user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO vocab_assignments
        (set_id, class_id, student_id, assigned_by, assigned_at)
        VALUES (?, ?, NULL, ?, ?)
        """,
        (set_id, class_id, user_id, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def assign_vocab_to_student(set_id, student_id, user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO vocab_assignments
        (set_id, class_id, student_id, assigned_by, assigned_at)
        VALUES (?, NULL, ?, ?, ?)
        """,
        (set_id, student_id, user_id, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_assigned_vocab_sets_for_student(student_id):
    classes = get_classes_for_student(student_id)
    class_ids = [cid for cid, cname, clevel in classes]

    conn = get_connection()
    cur = conn.cursor()

    params = [student_id]
    query = """
        SELECT DISTINCT vs.id, vs.name, vs.description, vs.level
        FROM vocab_assignments va
        JOIN vocab_sets vs ON va.set_id = vs.id
        LEFT JOIN class_students cs ON va.class_id = cs.class_id
        WHERE vs.is_active=1 AND (
            va.student_id = ?
    """
    if class_ids:
        placeholders = ",".join(["?"] * len(class_ids))
        query += f" OR va.class_id IN ({placeholders})"
        params.extend(class_ids)
    query += ")"
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def save_vocab_quiz_result(set_id, student_id, correct_count, total_count, mode="quiz"):
    conn = get_connection()
    cur = conn.cursor()
    percent = (correct_count / total_count * 100.0) if total_count > 0 else 0.0
    cur.execute(
        """
        INSERT INTO vocab_results
        (set_id, student_id, taken_at, mode,
         correct_count, total_count, percent)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (set_id, student_id, datetime.now().isoformat(),
         mode, correct_count, total_count, percent),
    )
    conn.commit()
    conn.close()


def get_vocab_results_for_set(set_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT vr.student_id, s.name, vr.taken_at,
               vr.correct_count, vr.total_count, vr.percent
        FROM vocab_results vr
        JOIN students s ON vr.student_id = s.id
        WHERE vr.set_id=?
        ORDER BY vr.taken_at DESC
        """,
        (set_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


# ============== 시험지 / 자료 파일 ==============

def save_uploaded_file(uploaded_file, student_id):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base, ext = os.path.splitext(uploaded_file.name)
    safe_ext = ext if ext else ".dat"
    filename = f"stu{student_id}_{timestamp}{safe_ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path, uploaded_file.name


def add_exam_document(student_id, subject, exam_type, exam_name,
                      exam_date_str, tags, memo, file_path,
                      original_name, uploaded_by):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO exam_documents
        (student_id, subject, exam_type, exam_name, exam_date,
         tags, memo, file_path, original_name, uploaded_by, uploaded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (student_id, subject, exam_type, exam_name, exam_date_str,
         tags, memo, file_path, original_name, uploaded_by,
         datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_exam_documents_for_student(student_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, subject, exam_type, exam_name, exam_date,
               tags, memo, file_path, original_name, uploaded_at
        FROM exam_documents
        WHERE student_id=?
        ORDER BY exam_date DESC, uploaded_at DESC
        """,
        (student_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


# ============== 테마 ==============

def apply_theme():
    theme = st.session_state.get("theme", "light")

    # 기본 색상 테마만 처리
    if theme == "dark":
        st.markdown(
            """
            <style>
            .stApp {
                background-color: #111111 !important;
                color: #F1F1F1 !important;
            }
            [data-testid="stSidebar"] {
                background-color: #181818 !important;
            }
            html, body, span, p, div, label, h1, h2, h3, h4, h5, h6,
            .stMarkdown, .stTextInput, .stTextArea, .stNumberInput,
            .stDateInput, .stSelectbox, .stRadio, .stTable, .stDataFrame {
                color: #F1F1F1 !important;
            }
            input, textarea {
                background-color: #1f1f1f !important;
                color: #F1F1F1 !important;
                border: 1px solid #555 !important;
            }
            .stSelectbox > div > div {
                background-color: #1f1f1f !important;
                color: #F1F1F1 !important;
            }
            table, th, td {
                color: #F1F1F1 !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <style>
            .stApp {
                background-color: #ffffff;
                color: #000000;
            }
            [data-testid="stSidebar"] {
                background-color: #f5f5f5;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )


    # 우측 상단 ... (ellipsis)만 숨기기
    st.markdown(
        """
        <style>
        header [data-testid="stToolbar"] {
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # 메인 컨테이너 위/아래 여백 최소화
    st.markdown(
        """
        <style>
        .main .block-container {
            padding-top: 1rem !important;
            padding-bottom: 1rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # 메인 컨테이너 위/아래 여백 최소화
    st.markdown(
        """
        <style>
        .main .block-container {
            padding-top: 1rem !important;
            padding-bottom: 1rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # 인쇄 시 사이드바/헤더 숨기기
    st.markdown(
        """
        <style>
        @media print {
            header, footer, [data-testid="stSidebar"] {
                display: none !important;
            }
            .main .block-container {
                padding-top: 0 !important;
                padding-bottom: 0 !important;
                max-width: 100% !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

def login_page():
    if "login_view" not in st.session_state:
        st.session_state["login_view"] = "login"
    view = st.session_state["login_view"]

    left, center, right = st.columns([1, 1, 1])

    with center:
        # ---------- 로고 + 학원명 ----------
        logo_left, logo_center, logo_right = st.columns([1, 2, 1])
        with logo_center:
            st.image("logo.png", width=260)
            st.markdown(
                "<p style='text-align:center; font-size:18px; "
                "margin-top:0.3rem; margin-bottom:0.4rem;'>"
                "DH SCHOOL • Cognoscenti</p>",
                unsafe_allow_html=True,
            )

        # -------------------- 로그인 화면 --------------------
        if view == "login":
            form_left, form_center, form_right = st.columns([1, 2, 1])
            with form_center:
                st.markdown(
                    "<h5 style='text-align:center; margin-top:0.2rem; "
                    "margin-bottom:0.5rem;'>🔐 로그인</h5>",
                    unsafe_allow_html=True,
                )

                username = st.text_input("아이디", key="login_username")
                password = st.text_input(
                    "비밀번호", type="password", key="login_password"
                )

                if st.button("로그인", use_container_width=True):
                    user = login_user(username, password)
                    if not user:
                        st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
                    else:
                        if not user.get("is_active", True):
                            st.error("사용이 중지된 계정입니다.")
                        elif user["role"] in ("admin", "student") and not user["is_approved"]:
                            st.warning("승인 대기 중입니다. 마스터 승인 후 로그인 가능합니다.")
                        else:
                            st.session_state["user"] = user
                            st.rerun()

                st.markdown(
                    "<hr style='margin-top:0.6rem; margin-bottom:0.6rem;'>",
                    unsafe_allow_html=True,
                )

                # 버튼을 세로로 배치 + 라벨에 명시적인 줄바꿈 추가
                if st.button(
                    "🧑‍🏫 관리자 계정\n신청하기",
                    use_container_width=True,
                    key="btn_admin_signup",
                ):
                    st.session_state["login_view"] = "signup"
                    st.rerun()

                if st.button(
                    "👨‍🎓 학생 계정\n만들기",
                    use_container_width=True,
                    key="btn_student_signup",
                ):
                    st.session_state["login_view"] = "student_signup"
                    st.rerun()

        # -------------------- 관리자 신청 화면 --------------------
        elif view == "signup":
            form_left, form_center, form_right = st.columns([1, 2, 1])
            with form_center:
                st.markdown(
                    "<h5 style='text-align:center; margin-top:0.2rem; "
                    "margin-bottom:0.5rem;'>🧑‍🏫 관리자 계정 신청</h5>",
                    unsafe_allow_html=True,
                )

                new_username = st.text_input(
                    "새 관리자 아이디", key="signup_username"
                )
                new_password = st.text_input(
                    "새 관리자 비밀번호",
                    type="password",
                    key="signup_password",
                )
                new_password2 = st.text_input(
                    "비밀번호 확인",
                    type="password",
                    key="signup_password2",
                )

                c1, c2 = st.columns(2)
                with c1:
                    if st.button("신청하기", use_container_width=True):
                        if not new_username or not new_password:
                            st.warning("아이디/비밀번호를 입력하세요.")
                        elif new_password != new_password2:
                            st.warning("비밀번호가 일치하지 않습니다.")
                        else:
                            ok = create_admin(new_username, new_password)
                            if ok:
                                st.success(
                                    "관리자 신청 완료! 마스터 승인 후 사용 가능합니다."
                                )
                                st.session_state["login_view"] = "login"
                                st.rerun()
                            else:
                                st.error("이미 존재하는 아이디입니다.")

                with c2:
                    if st.button("← 로그인으로 돌아가기", use_container_width=True):
                        st.session_state["login_view"] = "login"
                        st.rerun()

        # -------------------- 학생 계정 신청 화면 --------------------
        else:  # view == "student_signup"
            form_left, form_center, form_right = st.columns([1, 2, 1])
            with form_center:
                st.markdown(
                    "<h5 style='text-align:center; margin-top:0.2rem; "
                    "margin-bottom:0.5rem;'>👨‍🎓 학생 계정 신청</h5>",
                    unsafe_allow_html=True,
                )

                students = get_students()
                if not students:
                    st.info("먼저 학원에서 학생 등록 후, 계정 신청이 가능합니다.")
                else:
                    s_opts = {
                        f"{name} ({grade}, {school}) [ID:{sid}]": sid
                        for sid, name, school, grade, phone, memo in students
                    }
                    s_label = st.selectbox(
                        "본인 이름 선택 (학원에 등록된 정보와 일치해야 합니다.)",
                        list(s_opts.keys()),
                        key="stu_signup_student",
                    )
                    student_id = s_opts[s_label]

                    new_username = st.text_input("학생 아이디", key="stu_signup_username")
                    new_password = st.text_input(
                        "비밀번호", type="password", key="stu_signup_password"
                    )
                    new_password2 = st.text_input(
                        "비밀번호 확인", type="password", key="stu_signup_password2"
                    )

                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("신청하기", use_container_width=True):
                            if not new_username or not new_password:
                                st.warning("아이디와 비밀번호를 입력하세요.")
                            elif new_password != new_password2:
                                st.warning("비밀번호가 일치하지 않습니다.")
                            else:
                                ok = create_student_user(
                                    student_id, new_username, new_password
                                )
                                if ok:
                                    st.success(
                                        "학생 계정 신청 완료! 마스터 승인 후 로그인 가능합니다."
                                    )
                                    st.session_state["login_view"] = "login"
                                    st.rerun()
                                else:
                                    st.error("이미 사용 중인 아이디입니다.")
                    with c2:
                        if st.button("← 로그인으로 돌아가기", use_container_width=True):
                            st.session_state["login_view"] = "login"
                            st.rerun()


# ============== 사이드바 ==============

def render_sidebar():
    user = st.session_state.get("user")

    with st.sidebar:
        st.image("logo.png", width=150)
        st.markdown("**DH SCHOOL · Cognoscenti**")
        st.markdown("---")

        menu_value = None

        if user:
            st.markdown(f"**로그인:** `{user['username']}` ({user['role']})")
            if st.button("로그아웃", key="sidebar_logout_button"):
                st.session_state["user"] = None
                st.rerun()

            st.markdown("---")

            # ===== 학생 메뉴 =====
            if user["role"] == "student":
                menu_value = st.radio(
                    "학생 메뉴",
                    [
                        "대시보드",
                        "공지사항",
                        "내 학원 진도",
                        "내 학원 성적",
                        "내 학교 성적",
                        "내 시간표",
                        "내 단어장",
                        "내 시험지 자료",
                    ],
                    key="student_menu",
                )

            # ===== 관리자 / 마스터 메뉴 =====
            else:
                is_master = (user["role"] == "master")
                admin_items = [
                    "대시보드",          # 1
                    "공지 관리",         # 2
                    "학생 관리",         # (추가) – 이건 빼면 운영이 안 됨
                    "수업 관리",         # 3
                    "단어장 관리",       # 4
                    "성적 관리",         # 5
                    "시간표 관리",       # 6
                    "반(클래스) 관리",   # 7 (클래스관리)
                ]
                if is_master:
                    admin_items.append("관리자 승인")  # 8

                menu_value = st.radio(
                    "관리자 메뉴",
                    admin_items,
                    key="admin_menu",
                )

            st.markdown("---")
            st.markdown(
                "<div style='font-size:11px; opacity:0.8;'>테마 선택</div>",
                unsafe_allow_html=True,
            )
            theme_label = st.radio(
                "테마",
                ["라이트", "다크"],
                index=0 if st.session_state.get("theme", "light") == "light" else 1,
                horizontal=True,
                key="theme_radio",
            )
            st.session_state["theme"] = (
                "light" if theme_label == "라이트" else "dark"
            )
        else:
            st.info("로그인 후 메뉴를 사용할 수 있습니다.")

        return menu_value

# ============== 관리자 화면 ==============

def admin_student_management():

        import calendar
    from datetime import date

    base_date = st.date_input(
        "조회할 월 (임의 날짜 선택)",
        value=date.today(),
        key="admin_att_cal_base",
    )

    year = base_date.year
    month = base_date.month

    # ✅ 들여쓰기 레벨: 여기부터 전부 동일
    first_day = date(year, month, 1)
    last_day_num = calendar.monthrange(year, month)[1]
    first_wday = first_day.weekday()  # 월=0

    st.markdown("### 👦 학생 관리")

    students = get_students()

    # 학생 조회 시 선택된 학생을 세션에 보관
    if "selected_student_id" not in st.session_state:
        st.session_state["selected_student_id"] = students[0][0] if students else None

    # 탭 순서: 학생 조회 -> 학생 목록 -> 등록 -> 자료 업로드
    tab_view, tab_list, tab_add, tab_docs = st.tabs(
        ["학생 조회", "학생 목록", "학생 등록", "자료 업로드"]
    )

    # ------------------------------------------------------------------
    # 탭 1. 학생 조회
    # ------------------------------------------------------------------
    with tab_view:
        if not students:
            st.info("등록된 학생이 없습니다.")
        else:
            # 현재 선택된 학생
            id_to_student = {
                sid: (sid, name, school, grade, phone, memo)
                for sid, name, school, grade, phone, memo in students
            }
            # 학생 선택 드롭다운
            options = {
                f"{name} ({grade}, {school}) [ID:{sid}]": sid
                for sid, name, school, grade, phone, memo in students
            }

            # 기본값: 세션에 저장된 학생
            default_sid = st.session_state.get("selected_student_id")
            if default_sid not in id_to_student and students:
                default_sid = students[0][0]

            if default_sid in id_to_student:
                default_label = [
                    k for k, v in options.items() if v == default_sid
                ][0]
                idx = list(options.keys()).index(default_label)
            else:
                idx = 0

            sel_label = st.selectbox(
                "조회할 학생을 선택하세요",
                list(options.keys()),
                index=idx,
                key="student_view_select",
            )
            student_id = options[sel_label]
            st.session_state["selected_student_id"] = student_id

            sid, name, school, grade, phone, memo = id_to_student[student_id]

            st.markdown("#### 기본 정보")
            c1, c2 = st.columns(2)
            with c1:
                st.write(f"**이름:** {name}")
                st.write(f"**학교:** {school}")
                st.write(f"**학년:** {grade}")
            with c2:
                st.write(f"**학부모 연락처:** {phone}")
                st.write(f"**비고:** {memo}")

            st.markdown("---")

            # 7-1. 학생 시간표 (주간 캘린더 형식)
            st.markdown("#### 🗓 학생 시간표 (주간)")

            classes_for_stu = get_classes_for_student(sid)
            if not classes_for_stu:
                st.info("배정된 반이 없습니다.")
            else:
                class_ids = [cid for cid, cname, clevel in classes_for_stu]
                rows = get_timetables_for_classes(class_ids)

                if not rows:
                    st.info("등록된 시간표가 없습니다.")
                else:
                    # weekday: 0~6 → 월~일
                    weekday_names = ["월", "화", "수", "목", "금", "토", "일"]
                    timetable_map = {i: [] for i in range(7)}
                    for (
                        tid,
                        class_name,
                        weekday,
                        start_time,
                        end_time,
                        subject,
                        room,
                        teacher,
                        memo_tt,
                        class_id_row,
                    ) in rows:
                        text = f"{start_time}-{end_time}\n{class_name}\n{subject} / {teacher}"
                        timetable_map[weekday].append((start_time, text))

                    # 요일별 시간순 정렬
                    for w in timetable_map:
                        timetable_map[w].sort(key=lambda x: x[0])

                    # 가장 긴 요일의 수만큼 행 생성
                    max_len = max(len(v) for v in timetable_map.values())
                    cal_data = []
                    for row_idx in range(max_len):
                        row = {}
                        for w in range(7):
                            if row_idx < len(timetable_map[w]):
                                row[weekday_names[w]] = timetable_map[w][row_idx][1]
                            else:
                                row[weekday_names[w]] = ""
                        cal_data.append(row)

                    df_tt = pd.DataFrame(cal_data, columns=weekday_names)
                    st.dataframe(df_tt, use_container_width=True)

            st.markdown("---")

            # 7-2. 출결 / 일일 test / 과제 / 진도 / 출결(캘린더) / 부모님 번호 / 학년
            st.markdown("#### 🕒 출결 · 과제 · 일일 테스트 기록")

            # 최근 출결 100개
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                """
                SELECT date, checkin_time, status,
                       homework_status, daily_test_status
                FROM attendance
                WHERE student_id=?
                ORDER BY date DESC, checkin_time DESC
                LIMIT 100
                """,
                (sid,),
            )
            att_rows = cur.fetchall()
            conn.close()

            if not att_rows:
                st.info("출결 기록이 없습니다.")
            else:
                att_data = []
                for dt_str, t_str, status, hw, test in att_rows:
                    att_data.append(
                        {
                            "날짜": dt_str,
                            "시간": t_str,
                            "출결": status,
                            "과제": hw or "",
                            "일일테스트": test or "",
                        }
                    )
                df_att = pd.DataFrame(att_data)

                def color_cell(val):
                    if val == "정상출석":
                        return "background-color:#2f855a; color:white"
                    if val == "지각":
                        return "background-color:#d69e2e; color:white"
                    if val == "미인정결석":
                        return "background-color:#c53030; color:white"
                    if val == "○":
                        return "background-color:#2f855a; color:white"
                    if val == "△":
                        return "background-color:#d69e2e; color:white"
                    if val == "X":
                        return "background-color:#c53030; color:white"
                    return ""

                styled = df_att.style.applymap(
                    color_cell, subset=["출결", "과제", "일일테스트"]
                )
                st.dataframe(styled, use_container_width=True)

            st.markdown("---")

            # 진도 (학원 진도 테이블에서 불러오기 - 스키마에 맞춰 조정 가능)
            st.markdown("#### 📚 진도 기록")

            conn = get_connection()
            cur = conn.cursor()
            try:
                cur.execute(
                    """
                    SELECT date, subject, content, teacher, memo
                    FROM academy_progress
                    WHERE student_id=?
                    ORDER BY date DESC
                    """,
                    (sid,),
                )
                prog_rows = cur.fetchall()
            except Exception:
                prog_rows = []
            conn.close()

            if not prog_rows:
                st.info("진도 기록이 없습니다.")
            else:
                prog_data = []
                for dt_str, subj, content, teacher, memo_p in prog_rows:
                    prog_data.append(
                        {
                            "날짜": dt_str,
                            "과목": subj,
                            "내용": content,
                            "선생님": teacher,
                            "메모": memo_p or "",
                        }
                    )
                st.dataframe(
                    pd.DataFrame(prog_data),
                    use_container_width=True,
                )

            st.markdown("---")

            # 출결 캘린더 (월 단위)
            st.markdown("#### 📆 출결 캘린더 (월별)")

            base_date = st.date_input(
                "조회할 월 (임의 날짜 선택)",
                value=date.today(),
                key="stu_att_cal_base",
            )
            year = base_date.year
            month = base_date.month

            import calendar

            first_day = date(year, month, 1)
            last_day_num = calendar.monthrange(year, month)[1]

            # 날짜별 출결 요약 (학생 한 명 기준이므로 출결 종류 카운트)
            daily_status = {}
            conn = get_connection()
            cur = conn.cursor()
            for d in range(1, last_day_num + 1):
                dt_obj = date(year, month, d)
                d_str = dt_obj.strftime("%Y-%m-%d")
                cur.execute(
                    """
                    SELECT status
                    FROM attendance
                    WHERE student_id=? AND date=?
                    """,
                    (sid, d_str),
                )
                rows = cur.fetchall()
                if not rows:
                    daily_status[d] = ""
                else:
                    # 가장 나쁜 상태 우선으로 표기 (결석 > 지각 > 정상)
                    statuses = [r[0] for r in rows]
                    if "미인정결석" in statuses:
                        daily_status[d] = "결석"
                    elif "지각" in statuses:
                        daily_status[d] = "지각"
                    else:
                        daily_status[d] = "출석"
            conn.close()

    # 6x7 캘린더 매트릭스 생성
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    cal_matrix = [["" for _ in range(7)] for _ in range(6)]

    import calendar
from datetime import date

# base_date가 있든 없든, year/month를 먼저 확정
base_date = st.date_input(
    "조회할 월 (임의 날짜 선택)",
    value=date.today(),
    key="admin_att_cal_base",
)
year = base_date.year
month = base_date.month

# ✅ 여기서 무조건 first_day 정의
first_day = date(year, month, 1)
last_day_num = calendar.monthrange(year, month)[1]

# ✅ 이제 사용
first_wday = first_day.weekday()  # 월=0

    first_wday = first_day.weekday()  # 월=0
    week_idx = 0
    col_idx = first_wday

    for day in range(1, last_day_num + 1):
        status = daily_status.get(day, "")
        if status:
            cell = f"{day}\n{status}"
        else:
            cell = f"{day}"
        cal_matrix[week_idx][col_idx] = cell
        col_idx += 1
        if col_idx >= 7:
            col_idx = 0
            week_idx += 1

    df_cal = pd.DataFrame(cal_matrix, columns=weekdays)
    st.dataframe(df_cal, use_container_width=True)
    st.caption("셀에 날짜와 출결 상태(출석/지각/결석)가 표시됩니다.")

    # ------------------------------------------------------------------
    # 탭 2. 학생 목록  (검색 + 클릭 → 조회용 학생 세션에 반영)
    # ------------------------------------------------------------------
    with tab_list:
        if not students:
            st.info("등록된 학생이 없습니다.")
        else:
            # 현재 로그인 사용자 (마스터만 삭제 권한)
            user = st.session_state.get("user")
            is_master = user and user.get("role") == "master"

            # 이름 검색
            search = st.text_input(
                "이름 검색",
                key="student_list_search",
            ).strip()

            if search:
                filtered = [
                    (sid, name, school, grade, phone, memo)
                    for sid, name, school, grade, phone, memo in students
                    if search in name
                ]
            else:
                filtered = students

            if not filtered:
                st.info("검색 결과가 없습니다.")
            else:
                st.markdown("#### 학생 목록")
                st.caption(
                    "이름을 클릭하면 상단 '학생 조회' 탭에서 해당 학생의 상세 정보를 바로 볼 수 있습니다."
                )
                st.markdown("---")

                for sid, name, school, grade, phone, memo in filtered:
                    # 마스터일 때만 삭제 버튼용 컬럼 추가
                    if is_master:
                        c1, c2, c3, c4 = st.columns([2, 3, 2, 1])
                    else:
                        c1, c2, c3 = st.columns([2, 3, 2])
                        c4 = None

                    with c1:
                        # 이름을 버튼처럼 사용 -> 조회용 학생 세션 변경
                        if st.button(
                            name,
                            key=f"student_name_btn_{sid}",
                        ):
                            st.session_state["selected_student_id"] = sid
                            st.success(
                                f"'{name}' 학생이 조회 대상으로 설정되었습니다. "
                                "상단의 '학생 조회' 탭에서 확인하세요."
                            )
                            st.rerun()

                    with c2:
                        st.write(f"{school} / {grade}")

                    with c3:
                        st.write(f"부모님 연락처: {phone}")

                    # 삭제 버튼 (마스터 전용)
                    if is_master and c4 is not None:
                        with c4:
                            if st.button(
                                "삭제",
                                key=f"student_delete_btn_{sid}",
                            ):
                                delete_student(sid)
                                st.warning(f"'{name}' 학생이 삭제되었습니다.")
                                st.rerun()

    # ------------------------------------------------------------------
    # 탭 3. 학생 등록  (기존 등록 기능)
    # ------------------------------------------------------------------
    with tab_add:
        with st.form("add_student_form"):
            name = st.text_input("이름 *")
            school = st.text_input("학교")
            grade = st.text_input("학년 (예: 중2, 고1)")
            phone = st.text_input("부모님 연락처")
            memo = st.text_area("비고(선택)")
            submitted = st.form_submit_button("학생 등록")
            if submitted:
                if not name.strip():
                    st.warning("이름은 필수입니다.")
                else:
                    add_student(
                        name.strip(),
                        school.strip(),
                        grade.strip(),
                        phone.strip(),
                        memo.strip(),
                    )
                    st.success(f"'{name}' 학생이 등록되었습니다.")
                    st.rerun()

    # ------------------------------------------------------------------
    # 탭 4. 자료 업로드 (기존 시험지 / 자료 업로드)
    # ------------------------------------------------------------------
    with tab_docs:
        user = st.session_state["user"]
        students = get_students()
        if not students:
            st.info("먼저 학생을 등록해주세요.")
        else:
            opts = {
                f"{name} ({grade}, {school})": sid
                for sid, name, school, grade, phone, memo in students
            }
            label = st.selectbox(
                "학생 선택",
                list(opts.keys()),
                key="examdoc_student",
            )
            student_id = opts[label]

            subject = st.text_input("과목", key="examdoc_subject")
            exam_type = st.selectbox(
                "시험 종류",
                ["학교 중간", "학교 기말", "모의고사", "학원 테스트", "프린트", "기타"],
                key="examdoc_type",
            )
            exam_name = st.text_input("시험/자료 이름", key="examdoc_name")
            d = st.date_input(
                "시험/자료 날짜",
                value=date.today(),
                key="examdoc_date",
            )
            tags = st.text_input(
                "태그 (쉼표로 구분, 예: 중2,내신)",
                key="examdoc_tags",
            )
            memo = st.text_area("메모", key="examdoc_memo")

            uploaded = st.file_uploader(
                "시험지 / 자료 파일 업로드 (이미지 또는 PDF)",
                type=["pdf", "png", "jpg", "jpeg"],
                accept_multiple_files=False,
            )

            if st.button("자료 저장", key="examdoc_save"):
                if not uploaded:
                    st.warning("파일을 업로드해주세요.")
                else:
                    file_path, original_name = save_uploaded_file(
                        uploaded, student_id
                    )
                    add_exam_document(
                        student_id,
                        subject.strip(),
                        exam_type.strip(),
                        exam_name.strip(),
                        d.strftime("%Y-%m-%d"),
                        tags.strip(),
                        memo.strip(),
                        file_path,
                        original_name,
                        user["id"],
                    )
                    st.success("시험지 / 자료가 저장되었습니다.")

            st.markdown("#### 📄 해당 학생의 시험지 / 자료 목록")
            docs = get_exam_documents_for_student(student_id)
            if not docs:
                st.info("등록된 자료가 없습니다.")
            else:
                for (
                    doc_id,
                    subj,
                    etype,
                    ename,
                    edate,
                    dtags,
                    dmemo,
                    fpath,
                    oname,
                    uploaded_at,
                ) in docs:
                    title = f"{edate} • {subj} • {ename}"
                    with st.expander(title):
                        st.write(f"유형: {etype}")
                        st.write(f"태그: {dtags}")
                        st.write(f"메모: {dmemo}")
                        st.write(f"업로드 시간: {uploaded_at}")
                        try:
                            with open(fpath, "rb") as f:
                                file_bytes = f.read()
                            if fpath.lower().endswith(
                                (".png", ".jpg", ".jpeg")
                            ):
                                st.image(
                                    file_bytes,
                                    caption=oname,
                                    use_container_width=True,
                                )
                            else:
                                st.download_button(
                                    label="📎 파일 다운로드",
                                    data=file_bytes,
                                    file_name=oname,
                                    mime="application/pdf",
                                )
                        except FileNotFoundError:
                            st.error(f"파일을 찾을 수 없습니다. (경로: {fpath})")


def admin_class_management():
    st.markdown("### 🏫 반(클래스) 관리")

    classes = get_classes()
    students = get_students()

    # 탭: 반 목록 / 반 배치 / 반 생성 및 수정
    tab_list, tab_assign, tab_edit = st.tabs(
        ["반 목록", "반 배치", "반 생성 및 수정"]
    )

    # ------------------------------------------------------------------
    # 탭 1. 반 목록
    # ------------------------------------------------------------------
    with tab_list:
        if not classes:
            st.info("생성된 반이 없습니다.")
        else:
            data = []
            for cid, name, level, memo in classes:
                data.append(
                    {
                        "ID": cid,
                        "반 이름": name,
                        "레벨": level,
                        "메모": memo,
                    }
                )
            st.dataframe(pd.DataFrame(data), use_container_width=True)

    # ------------------------------------------------------------------
    # 탭 2. 반 배치 (학생 → 반)
    # ------------------------------------------------------------------
    with tab_assign:
        if not classes or not students:
            st.info("반과 학생이 모두 존재해야 합니다.")
        else:
            c_opts = {
                f"{name} ({level})": cid
                for cid, name, level, memo in classes
            }
            s_opts = {
                f"{name} ({grade}, {school})": sid
                for sid, name, school, grade, phone, memo in students
            }

            c_label = st.selectbox(
                "반 선택",
                list(c_opts.keys()),
                key="class_assign_class",
            )
            s_label = st.selectbox(
                "학생 선택",
                list(s_opts.keys()),
                key="class_assign_student",
            )

            class_id = c_opts[c_label]
            student_id = s_opts[s_label]

            if st.button("학생을 반에 배치", key="btn_assign_student_to_class"):
                assign_student_to_class(student_id, class_id)
                st.success("학생이 반에 배치되었습니다.")

    # ------------------------------------------------------------------
    # 탭 3. 반 생성 및 수정/삭제
    # ------------------------------------------------------------------
    with tab_edit:
        col_new, col_edit = st.columns(2)

        # ---------- 새 반 생성 ----------
        with col_new:
            st.markdown("#### 새 반 생성")

            new_name = st.text_input("새 반 이름", key="class_new_name")
            new_level = st.text_input("새 반 레벨/학년", key="class_new_level")
            new_memo = st.text_area("새 반 메모", key="class_new_memo")

            if st.button("반 생성", key="btn_class_create"):
                if not new_name.strip():
                    st.warning("반 이름은 필수입니다.")
                else:
                    add_class(new_name.strip(), new_level.strip(), new_memo.strip())
                    st.success(f"'{new_name}' 반이 생성되었습니다.")
                    st.rerun()

        # ---------- 기존 반 수정/삭제 ----------
        with col_edit:
            st.markdown("#### 기존 반 수정 / 삭제")

            if not classes:
                st.info("수정할 반이 없습니다.")
            else:
                edit_opts = {
                    f"{name} ({level}) [ID:{cid}]": cid
                    for cid, name, level, memo in classes
                }
                sel_label = st.selectbox(
                    "수정할 반 선택",
                    list(edit_opts.keys()),
                    key="class_edit_select",
                )
                sel_id = edit_opts[sel_label]

                # 선택된 반 정보 찾기
                sel_name, sel_level, sel_memo = None, None, ""
                for cid, name, level, memo in classes:
                    if cid == sel_id:
                        sel_name, sel_level, sel_memo = name, level, memo or ""
                        break

                edit_name = st.text_input(
                    "반 이름(수정)",
                    value=sel_name,
                    key=f"class_edit_name_{sel_id}",
                )
                edit_level = st.text_input(
                    "레벨/학년(수정)",
                    value=sel_level,
                    key=f"class_edit_level_{sel_id}",
                )
                edit_memo = st.text_area(
                    "메모(수정)",
                    value=sel_memo,
                    key=f"class_edit_memo_{sel_id}",
                )

                b1, b2 = st.columns(2)
                with b1:
                    if st.button("변경 내용 저장", key=f"class_save_{sel_id}"):
                        if not edit_name.strip():
                            st.warning("반 이름은 비울 수 없습니다.")
                        else:
                            update_class(
                                sel_id,
                                edit_name.strip(),
                                edit_level.strip(),
                                edit_memo.strip(),
                            )
                            st.success("반 정보가 수정되었습니다.")
                            st.rerun()
                with b2:
                    if st.button("반 삭제", key=f"class_delete_{sel_id}"):
                        delete_class(sel_id)
                        st.warning(
                            f"반(ID:{sel_id})이 삭제되었습니다. "
                            "해당 반과 연결된 시간표/배정/성적/출석/단어장도 함께 정리되었습니다."
                        )
                        st.rerun()

def update_school_score(score_id, date_str, subject, exam_name,
                        score, max_score, memo):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE school_scores
        SET date=?, subject=?, exam_name=?, score=?, max_score=?, memo=?
        WHERE id=?
        """,
        (date_str, subject, exam_name, score, max_score, memo, score_id),
    )
    conn.commit()
    conn.close()


def delete_school_score(score_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM school_scores WHERE id=?", (score_id,))
    conn.commit()
    conn.close()


def update_academy_score(score_id, date_str, subject, test_name,
                         score, max_score, memo):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE academy_scores
        SET date=?, subject=?, test_name=?, score=?, max_score=?, memo=?
        WHERE id=?
        """,
        (date_str, subject, test_name, score, max_score, memo, score_id),
    )
    conn.commit()
    conn.close()


def delete_academy_score(score_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM academy_scores WHERE id=?", (score_id,))
    conn.commit()
    conn.close()


def update_academy_progress_record(progress_id, date_str, subject,
                                   unit, memo):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE academy_progress
        SET date=?, subject=?, unit=?, memo=?
        WHERE id=?
        """,
        (date_str, subject, unit, memo, progress_id),
    )
    conn.commit()
    conn.close()


def delete_academy_progress_record(progress_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM academy_progress WHERE id=?", (progress_id,))
    conn.commit()
    conn.close()


def update_attendance_record(att_id, status, homework_status,
                             daily_test_status):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE attendance
        SET status=?, homework_status=?, daily_test_status=?
        WHERE id=?
        """,
        (status, homework_status, daily_test_status, att_id),
    )
    conn.commit()
    conn.close()


def delete_attendance_record(att_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM attendance WHERE id=?", (att_id,))
    conn.commit()
    conn.close()


def admin_school_scores():
    st.markdown("### 🏫 학교 성적 관리")
    user = st.session_state["user"]
    students = get_students()

    # 탭 순서: 성적 입력 -> 성적 조회/그래프
    tab1, tab2 = st.tabs(["성적 입력", "성적 조회/그래프"])

    # =========================
    # 1. 성적 입력 (학기 단위)
    # =========================
    with tab1:
        if not students:
            st.info("학생이 없습니다.")
        else:
            opts = {
                f"{name} ({grade}, {school})": sid
                for sid, name, school, grade, phone, memo in students
            }
            label = st.selectbox(
                "학생 선택",
                list(opts.keys()),
                key="school_score_student_select",
            )
            student_id = opts[label]

            # 실제 시험 날짜(성적 입력일과는 별개로 보관)
            d = st.date_input(
                "시험 일자",
                value=date.today(),
                key="school_score_date",
            )

            # 자주 사용하는 과목 목록 + 직접 입력 선택
            common_subjects = get_common_subjects()

            subject_mode = st.radio(
                "과목 입력 방식",
                ["목록에서 선택", "직접 입력"],
                key="school_score_subject_mode",
                horizontal=True,
            )

            if subject_mode == "목록에서 선택":
                subject = st.selectbox(
                    "과목 선택",
                    common_subjects,
                    key="school_score_subject_select",
                )
            else:
                subject = st.text_input(
                    "과목 (예: 수학, 영어)",
                    key="school_score_subject_manual",
                )

            # === 새로 추가: 학년 / 학기 / 시험 구분 ===
            col_g, col_s, col_t = st.columns(3)
            with col_g:
                exam_grade = st.selectbox(
                    "학년",
                    ["1학년", "2학년", "3학년"],
                    key="school_exam_grade",
                )
            with col_s:
                exam_semester = st.selectbox(
                    "학기",
                    ["1학기", "2학기"],
                    key="school_exam_semester",
                )
            with col_t:
                exam_type = st.selectbox(
                    "시험 구분",
                    ["중간고사", "기말고사", "단원평가", "학력평가", "기타"],
                    key="school_exam_type",
                )

            custom_suffix = st.text_input(
                "시험명 추가 설명 (선택, 예: 전범위, 수행평가 등)",
                key="school_exam_suffix",
            )

            # 자동 생성되는 시험명 미리보기
            if custom_suffix.strip():
                exam_name = f"{exam_grade} {exam_semester} {exam_type} {custom_suffix.strip()}"
            else:
                exam_name = f"{exam_grade} {exam_semester} {exam_type}"

            st.markdown(f"**시험명 미리보기:** `{exam_name}`")

            score = st.number_input(
                "점수",
                min_value=0.0,
                max_value=200.0,
                value=0.0,
                key="school_score_score",
            )
            max_score = st.number_input(
                "만점",
                min_value=0.0,
                max_value=200.0,
                value=100.0,
                key="school_score_max_score",
            )
            memo = st.text_area(
                "메모 (선택)",
                key="school_score_memo",
            )

            if st.button("학교 성적 저장", key="school_score_save_btn"):
                if not subject.strip():
                    st.warning("과목은 필수입니다.")
                else:
                    add_school_score(
                        student_id,
                        d.strftime("%Y-%m-%d"),
                        subject.strip(),
                        exam_name.strip(),
                        score,
                        max_score,
                        memo.strip(),
                        user["id"],
                    )
                    st.success("학교 성적이 저장되었습니다.")

    # =========================
    # 2. 성적 조회/그래프 (학기 기준 필터)
    # =========================
    with tab2:
        if not students:
            st.info("학생이 없습니다.")
        else:
            opts = {
                f"{name} ({grade}, {school})": sid
                for sid, name, school, grade, phone, memo in students
            }
            label = st.selectbox(
                "조회할 학생",
                list(opts.keys()),
                key="view_school_student",
            )
            student_id = opts[label]

            # 과목 필터
            subject = st.text_input(
                "과목 필터 (비우면 전체)",
                key="view_school_subject",
            ).strip()
            subject_filter = subject if subject else None

            # === 새로 추가: 학년/학기/시험 구분 필터 ===
            col_g, col_s, col_t = st.columns(3)
            with col_g:
                filter_grade = st.selectbox(
                    "학년 필터",
                    ["(전체)", "1학년", "2학년", "3학년"],
                    key="view_school_grade_filter",
                )
            with col_s:
                filter_semester = st.selectbox(
                    "학기 필터",
                    ["(전체)", "1학기", "2학기"],
                    key="view_school_semester_filter",
                )
            with col_t:
                filter_type = st.selectbox(
                    "시험 구분 필터",
                    ["(전체)", "중간고사", "기말고사", "단원평가", "학력평가", "기타"],
                    key="view_school_type_filter",
                )

            # DB에서 가져오기
            rows = get_scores_for_student(
                "school_scores", student_id, subject_filter
            )

            if not rows:
                st.info("성적 기록이 없습니다.")
            else:
                data = []
                for dt, subj, exam_name, score, max_score in rows:
                    data.append(
                        {
                            "날짜": dt,
                            "과목": subj,
                            "시험명": exam_name,
                            "점수": score,
                            "만점": max_score,
                        }
                    )
                df = pd.DataFrame(data)

                # ---- 학년/학기/시험구분 필터링 (exam_name 문자열 기반) ----
                def match_filter(row):
                    name = str(row["시험명"])
                    if filter_grade != "(전체)" and filter_grade not in name:
                        return False
                    if filter_semester != "(전체)" and filter_semester not in name:
                        return False
                    if filter_type != "(전체)" and filter_type not in name:
                        return False
                    return True

                df = df[df.apply(match_filter, axis=1)]

                if df.empty:
                    st.info("선택한 필터 조건에 해당하는 성적이 없습니다.")
                else:
                    st.dataframe(df, use_container_width=True)

                    df_plot = df.copy()
                    df_plot["날짜"] = pd.to_datetime(df_plot["날짜"])
                    df_plot.set_index("날짜", inplace=True)
                    st.line_chart(df_plot["점수"])

def admin_academy_progress():
    st.markdown("### 📚 진도 관리")
    user = st.session_state["user"]
    students = get_students()
    classes = get_classes()

    # 탭 순서: 반 단위 진도 입력 -> 개인 진도 입력 -> 진도 조회
    tab_class, tab_person, tab_view = st.tabs(
        ["반 단위 진도 입력", "개인 진도 입력", "진도 조회"]
    )

    # =========================
    # 1. 반 단위 진도 입력
    # =========================
    with tab_class:
        if not classes:
            st.info("반이 없습니다.")
        else:
            c_opts = {
                f"{name} ({level})": cid
                for cid, name, level, memo in classes
            }
            c_label = st.selectbox(
                "반 선택",
                list(c_opts.keys()),
                key="apc_class_select",
            )
            class_id = c_opts[c_label]

            d = st.date_input(
                "일자",
                value=date.today(),
                key="apc_date",
            )
            subject_options2 = get_common_subjects()
            if subject_options2:
                subject_choice2 = st.selectbox(
                    "과목 선택",
                    ["(직접 입력)"] + subject_options2,
                    key="apc_subject_choice",
                )
                if subject_choice2 == "(직접 입력)":
                    subject = st.text_input(
                        "과목 (직접 입력)",
                        key="apc_subject_manual",
                    )
                else:
                    subject = subject_choice2
            else:
                subject = st.text_input("과목", key="apc_subject_manual")
            unit = st.text_input("단원/교재/페이지", key="apc_unit")
            memo = st.text_area("공통 메모", key="apc_memo")

            # 해당 반 학생 목록
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                """
                SELECT s.id, s.name, s.school, s.grade
                FROM class_students cs
                JOIN students s ON cs.student_id=s.id
                WHERE cs.class_id=?
                ORDER BY s.name
                """,
                (class_id,),
            )
            class_students = cur.fetchall()
            conn.close()

            if not class_students:
                st.info("해당 반에 학생이 없습니다.")
            else:
                st.write(f"해당 반 학생 수: {len(class_students)}명")
                if st.button(
                    "반 전체에 동일 진도 저장",
                    key="apc_save_for_all",
                ):
                    if not subject.strip():
                        st.warning("과목은 필수입니다.")
                    else:
                        for sid, name, school, grade in class_students:
                            add_academy_progress(
                                sid,
                                class_id,
                                d.strftime("%Y-%m-%d"),
                                subject.strip(),
                                unit.strip(),
                                memo.strip(),
                                user["id"],
                            )
                        st.success("반 전체 진도가 저장되었습니다.")

    # =========================
    # 2. 개인 진도 입력
    # =========================
    with tab_person:
        if not students:
            st.info("학생이 없습니다.")
        else:
            s_opts = {
                f"{name} ({grade}, {school})": sid
                for sid, name, school, grade, phone, memo in students
            }
            s_label = st.selectbox(
                "학생 선택",
                list(s_opts.keys()),
                key="ap_student_select",
            )
            student_id = s_opts[s_label]

            c_id = None
            if classes:
                c_opts = {"(선택 안함)": None}
                c_opts.update(
                    {
                        f"{name} ({level})": cid
                        for cid, name, level, memo in classes
                    }
                )
                c_label = st.selectbox(
                    "반 선택 (선택사항)",
                    list(c_opts.keys()),
                    key="ap_class_select",
                )
                c_id = c_opts[c_label]

            d = st.date_input(
                "일자",
                value=date.today(),
                key="ap_date",
            )
            subject_options = get_common_subjects()
            if subject_options:
                subject_choice = st.selectbox(
                    "과목 선택",
                    ["(직접 입력)"] + subject_options,
                    key="ap_subject_choice",
                )
                if subject_choice == "(직접 입력)":
                    subject = st.text_input(
                        "과목 (직접 입력)",
                        key="ap_subject_manual",
                    )
                else:
                    subject = subject_choice
            else:
                subject = st.text_input("과목", key="ap_subject_manual")
            unit = st.text_input("단원/교재/페이지", key="ap_unit")
            memo = st.text_area("메모", key="ap_memo")

            if st.button("진도 저장(개인)", key="ap_save_person"):
                if not subject.strip():
                    st.warning("과목은 필수입니다.")
                else:
                    add_academy_progress(
                        student_id,
                        c_id,
                        d.strftime("%Y-%m-%d"),
                        subject.strip(),
                        unit.strip(),
                        memo.strip(),
                        user["id"],
                    )
                    st.success("학원 진도가 저장되었습니다.")

    # =========================
    # 3. 진도 조회
    # =========================
    with tab_view:
        students = get_students()
        if not students:
            st.info("학생이 없습니다.")
        else:
            s_opts = {"(전체)": None}
            s_opts.update(
                {
                    f"{name} ({grade}, {school})": sid
                    for sid, name, school, grade, phone, memo in students
                }
            )
            s_label = st.selectbox(
                "학생 필터",
                list(s_opts.keys()),
                key="apv_student_select",
            )
            student_id = s_opts[s_label]

            subject = st.text_input(
                "과목 필터 (비우면 전체)",
                key="apv_subject",
            ).strip()
            subject_filter = subject if subject else None

            conn = get_connection()
            cur = conn.cursor()
            query = """
                SELECT p.date, s.name, c.name, p.subject, p.unit, p.memo
                FROM academy_progress p
                JOIN students s ON p.student_id=s.id
                LEFT JOIN classes c ON p.class_id=c.id
                WHERE 1=1
            """
            params = []
            if student_id:
                query += " AND p.student_id=?"
                params.append(student_id)
            if subject_filter:
                query += " AND p.subject=?"
                params.append(subject_filter)
            query += " ORDER BY p.date DESC"
            cur.execute(query, params)
            rows = cur.fetchall()
            conn.close()

            if not rows:
                st.info("진도 기록이 없습니다.")
            else:
                data = []
                for dt, name, cname, subj, unit, memo in rows:
                    data.append(
                        {
                            "날짜": dt,
                            "학생": name,
                            "반": cname,
                            "과목": subj,
                            "단원/교재": unit,
                            "메모": memo,
                        }
                    )
                st.dataframe(pd.DataFrame(data), use_container_width=True)

def admin_lesson_management():
    """
    수업 관리:
    - 탭1: 반별 수업 관리 (이전 진도/숙제 + 오늘 진도/다음 숙제 + 반 단위 출석)
    - 탭2: 진도 관리 (전체)  -> 기존 admin_academy_progress 재사용
    - 탭3: 출석 관리 (일별)  -> 기존 admin_attendance_management 재사용
    """
    st.markdown("### 📘 수업 / 진도 / 출석 관리")

    user = st.session_state["user"]
    classes = get_classes()

    tab_overview, tab_progress, tab_attend = st.tabs(
        ["반별 수업 관리", "진도 관리 (전체)", "출석 관리 (일별)"]
    )

    # =============================
    # 탭1. 반별 수업 관리
    # =============================
    with tab_overview:
        if not classes:
            st.info("반이 없습니다. 먼저 반을 생성하세요.")
            return

        # 반 선택
        c_opts = {
            f"{name} ({level})": cid
            for cid, name, level, memo in classes
        }
        class_label = st.selectbox(
            "수업 반 선택",
            list(c_opts.keys()),
            key="lesson_class_select",
        )
        class_id = c_opts[class_label]

        # ===== 1) 이전 진도 / 이전 숙제 =====
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT date, subject, unit, memo
            FROM academy_progress
            WHERE class_id=?
            ORDER BY date DESC, id DESC
            LIMIT 1
            """,
            (class_id,),
        )
        last_row = cur.fetchone()
        conn.close()

        st.markdown("#### 이전 진도 / 이전 숙제")

        if last_row:
            last_date_str, last_subj, last_unit, last_memo = last_row

            # '이전 수업일'을 년도/월/일/요일까지 표기
            try:
                dt = datetime.strptime(last_date_str, "%Y-%m-%d")
                weekday_ko = ["월", "화", "수", "목", "금", "토", "일"][dt.weekday()]
                pretty_date = dt.strftime("%Y-%m-%d") + f" ({weekday_ko})"
            except Exception:
                pretty_date = last_date_str

            st.write(f"- **이전 수업일:** {pretty_date}")
            st.write(f"- **이전 진도:** {last_unit or '(기록 없음)'}")
            st.write(f"- **이전 숙제:** {last_memo or '(기록 없음)'}")
            if last_subj:
                st.write(f"- **과목:** {last_subj}")
        else:
            st.info("이 반의 진도 기록이 아직 없습니다.")

        st.markdown("---")

        # ===== 2) 오늘 진도 + 다음 숙제 입력 (반 전체) =====
        st.markdown("#### 오늘 진도 및 다음 숙제 입력 (반 전체)")

        d = st.date_input(
            "수업 일자",
            value=date.today(),
            key="lesson_date",
        )

        # 과목 선택 (자주 사용하는 과목 + 직접입력)
        default_subject = last_row[1] if last_row and last_row[1] else ""
        subject_options = get_common_subjects()
        if subject_options:
            base_list = ["(직접 입력)"] + subject_options
            default_index = 0
            if default_subject and default_subject in subject_options:
                default_index = 1 + subject_options.index(default_subject)

            subject_choice = st.selectbox(
                "오늘 과목 선택",
                base_list,
                index=default_index,
                key="lesson_subject_choice",
            )
            if subject_choice == "(직접 입력)":
                subject_today = st.text_input(
                    "오늘 과목 (직접 입력)",
                    value=default_subject,
                    key="lesson_subject_manual",
                )
            else:
                subject_today = subject_choice
        else:
            subject_today = st.text_input(
                "오늘 과목",
                value=default_subject,
                key="lesson_subject_manual_only",
            )

        unit_today = st.text_input(
            "오늘 진도 (단원/교재/페이지)",
            key="lesson_unit_today",
        )
        homework_next = st.text_area(
            "다음 시간까지 숙제",
            key="lesson_homework_next",
        )

        if st.button(
            "반 전체 진도 + 숙제 저장",
            key="lesson_save_progress",
        ):
            if not subject_today.strip():
                st.warning("오늘 과목은 필수입니다.")
            elif not unit_today.strip():
                st.warning("오늘 진도는 필수입니다.")
            else:
                # 해당 반 학생 목록
                conn = get_connection()
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT s.id, s.name, s.school, s.grade
                    FROM class_students cs
                    JOIN students s ON cs.student_id = s.id
                    WHERE cs.class_id=?
                    ORDER BY s.name
                    """,
                    (class_id,),
                )
                class_students = cur.fetchall()
                conn.close()

                if not class_students:
                    st.warning("해당 반에 학생이 없습니다.")
                else:
                    date_str = d.strftime("%Y-%m-%d")
                    for sid, name, school, grade in class_students:
                        add_academy_progress(
                            student_id=sid,
                            class_id=class_id,
                            date_str=date_str,
                            subject=subject_today.strip(),
                            unit=unit_today.strip(),
                            memo=homework_next.strip(),
                            recorded_by=user["id"],
                        )
                    st.success(
                        f"{class_label} 반 전체에 오늘 진도와 다음 숙제가 저장되었습니다."
                    )

        st.markdown("---")

        # ===== 3) 학생별 출석 / 일일테스트 / 과제 입력 =====
        st.markdown("#### 학생별 출석 / 일일 테스트 / 과제 입력")

        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT s.id, s.name, s.school, s.grade
            FROM class_students cs
            JOIN students s ON cs.student_id = s.id
            WHERE cs.class_id=?
            ORDER BY s.name
            """,
            (class_id,),
        )
        class_students = cur.fetchall()
        conn.close()

        if not class_students:
            st.info("해당 반에 학생이 없습니다.")
        else:
            st.caption(
                "각 학생별로 출석 / 과제 / 일일테스트 상태를 선택한 뒤, "
                "아래 버튼으로 한 번에 저장합니다."
            )

            # 출석 날짜 선택 (여기서도 날짜 선택 가능)
            att_date_for_class = st.date_input(
                "출석 기록 날짜",
                value=date.today(),
                key="lesson_att_date",
            )
            att_date_str = att_date_for_class.strftime("%Y-%m-%d")

            for sid, name, school, grade in class_students:
                c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
                with c1:
                    st.markdown(f"**{name} ({grade}, {school})**")
                with c2:
                    st.selectbox(
                        "출결",
                        ["정상출석", "지각", "미인정결석"],
                        key=f"lesson_status_{class_id}_{sid}",
                    )
                with c3:
                    st.selectbox(
                        "과제",
                        ["○", "△", "X"],
                        key=f"lesson_hw_{class_id}_{sid}",
                    )
                with c4:
                    st.selectbox(
                        "일일 테스트",
                        ["○", "△", "X"],
                        key=f"lesson_test_{class_id}_{sid}",
                    )

            if st.button(
                "오늘 수업 출석/과제/일일테스트 저장",
                key="lesson_save_attendance",
            ):
                saved_count = 0
                for sid, name, school, grade in class_students:
                    status = st.session_state.get(
                        f"lesson_status_{class_id}_{sid}", "정상출석"
                    )
                    hw = st.session_state.get(
                        f"lesson_hw_{class_id}_{sid}", "○"
                    )
                    test = st.session_state.get(
                        f"lesson_test_{class_id}_{sid}", "○"
                    )
                    add_attendance(
                        student_id=sid,
                        class_id=class_id,
                        status=status,
                        homework_status=hw,
                        daily_test_status=test,
                        via="수업관리",
                        recorded_by=user["id"],
                        date_str=att_date_str,   # ← 날짜 반영
                    )
                    saved_count += 1

                st.success(
                    f"{class_label} 반 학생 {saved_count}명의 출석/과제/일일테스트가 저장되었습니다."
                )

    # =============================
    # 탭2. 진도 관리 (전체)
    # =============================
    with tab_progress:
        # 기존 진도 관리 화면 그대로 재사용
        admin_academy_progress()

    # =============================
    # 탭3. 출석 관리 (일별)
    # =============================
    with tab_attend:
        # 기존 출석 관리 화면 그대로 재사용
        admin_attendance_management()

def admin_score_management():
    """성적 관리 메인: 탭으로 학원/학교 나누기"""
    tab_academy, tab_school = st.tabs(["학원 성적", "학교 성적"])

    # 기존 함수 재사용 (내부에서 또 탭으로 입력/조회 나뉘는 구조 그대로 유지)
    with tab_academy:
        admin_academy_scores()

    with tab_school:
        admin_school_scores()


def admin_scores_management():
    st.markdown("### 📊 성적 관리")
    user = st.session_state["user"]
    students = get_students()
    classes = get_classes()

    tab1, tab2 = st.tabs(["학교 성적", "학원 성적"])

    # ---------- 학교 성적 ----------
    with tab1:
        st.markdown("#### 학교 성적 입력 / 조회")
        sub_tab1, sub_tab2 = st.tabs(["성적 입력", "성적 조회/그래프"])

        with sub_tab1:
            if not students:
                st.info("학생이 없습니다.")
            else:
                opts = {
                    f"{name} ({grade}, {school})": sid
                    for sid, name, school, grade, phone, memo in students
                }
                label = st.selectbox("학생 선택", list(opts.keys()))
                student_id = opts[label]
                d = st.date_input("일자", value=date.today())
                subject = st.text_input("과목 (예: 수학)")
                exam_name = st.text_input("시험명 (예: 중간고사)")
                score = st.number_input(
                    "점수", min_value=0.0, max_value=200.0, value=0.0
                )
                max_score = st.number_input(
                    "만점", min_value=0.0, max_value=200.0, value=100.0
                )
                memo = st.text_area("메모")
                if st.button("학교 성적 저장"):
                    if not subject.strip():
                        st.warning("과목은 필수입니다.")
                    else:
                        add_school_score(
                            student_id,
                            d.strftime("%Y-%m-%d"),
                            subject.strip(),
                            exam_name.strip(),
                            score,
                            max_score,
                            memo.strip(),
                            user["id"],
                        )
                        st.success("학교 성적이 저장되었습니다.")

        with sub_tab2:
            if not students:
                st.info("학생이 없습니다.")
            else:
                opts = {
                    f"{name} ({grade}, {school})": sid
                    for sid, name, school, grade, phone, memo in students
                }
                label = st.selectbox(
                    "조회할 학생",
                    list(opts.keys()),
                    key="view_school_student",
                )
                student_id = opts[label]
                subject = st.text_input(
                    "과목 필터 (비우면 전체)",
                    key="view_school_subject",
                ).strip()
                subject_filter = subject if subject else None

                rows = get_scores_for_student(
                    "school_scores", student_id, subject_filter
                )
                if not rows:
                    st.info("성적 기록이 없습니다.")
                else:
                    data = []
                    for dt, subj, exam_name, score, max_score in rows:
                        data.append(
                            {
                                "날짜": dt,
                                "과목": subj,
                                "시험명": exam_name,
                                "점수": score,
                                "만점": max_score,
                            }
                        )
                    df = pd.DataFrame(data)
                    st.dataframe(df, use_container_width=True)

                    df_plot = df.copy()
                    df_plot["날짜"] = pd.to_datetime(df_plot["날짜"])
                    df_plot.set_index("날짜", inplace=True)
                    st.line_chart(df_plot["점수"])

    # ---------- 학원 성적 ----------
    with tab2:
        st.markdown("#### 학원 성적 입력 / 조회")
        sub_tab1, sub_tab2 = st.tabs(["성적 입력", "성적 조회/그래프"])

        with sub_tab1:
            if not students:
                st.info("학생이 없습니다.")
            else:
                s_opts = {
                    f"{name} ({grade}, {school})": sid
                    for sid, name, school, grade, phone, memo in students
                }
                s_label = st.selectbox(
                    "학생 선택", list(s_opts.keys()), key="as_student"
                )
                student_id = s_opts[s_label]

                c_id = None
                if classes:
                    c_opts = {"(선택 안함)": None}
                    c_opts.update(
                        {
                            f"{name} ({level})": cid
                            for cid, name, level, memo in classes
                        }
                    )
                    c_label = st.selectbox(
                        "반 선택(선택)",
                        list(c_opts.keys()),
                        key="as_class",
                    )
                    c_id = c_opts[c_label]

                d = st.date_input("일자", value=date.today(), key="as_date")
                subject = st.text_input("과목", key="as_subject")
                test_name = st.text_input(
                    "시험명 (예: 주간테스트)", key="as_test_name"
                )
                score = st.number_input(
                    "점수", min_value=0.0, max_value=200.0,
                    value=0.0, key="as_score",
                )
                max_score = st.number_input(
                    "만점", min_value=0.0, max_value=200.0,
                    value=100.0, key="as_max_score",
                )
                memo = st.text_area("메모", key="as_memo")

                if st.button("학원 성적 저장"):
                    if not subject.strip():
                        st.warning("과목은 필수입니다.")
                    else:
                        add_academy_score(
                            student_id,
                            c_id,
                            d.strftime("%Y-%m-%d"),
                            subject.strip(),
                            test_name.strip(),
                            score,
                            max_score,
                            memo.strip(),
                            user["id"],
                        )
                        st.success("학원 성적이 저장되었습니다.")

        with sub_tab2:
            if not students:
                st.info("학생이 없습니다.")
            else:
                s_opts = {
                    f"{name} ({grade}, {school})": sid
                    for sid, name, school, grade, phone, memo in students
                }
                s_label = st.selectbox(
                    "조회할 학생",
                    list(s_opts.keys()),
                    key="asv_student",
                )
                student_id = s_opts[s_label]
                subject = st.text_input(
                    "과목 필터 (비우면 전체)",
                    key="asv_subject",
                ).strip()
                subject_filter = subject if subject else None

                rows = get_scores_for_student(
                    "academy_scores", student_id, subject_filter
                )
                if not rows:
                    st.info("성적 기록이 없습니다.")
                else:
                    data = []
                    for dt, subj, test_name, score, max_score in rows:
                        data.append(
                            {
                                "날짜": dt,
                                "과목": subj,
                                "시험명": test_name,
                                "점수": score,
                                "만점": max_score,
                            }
                        )
                    df = pd.DataFrame(data)
                    st.dataframe(df, use_container_width=True)

                    df_plot = df.copy()
                    df_plot["날짜"] = pd.to_datetime(df_plot["날짜"])
                    df_plot.set_index("날짜", inplace=True)
                    st.line_chart(df_plot["점수"])


def admin_academy_scores():
    st.markdown("### 📊 학원 성적 관리")
    user = st.session_state["user"]
    students = get_students()
    classes = get_classes()

    tab1, tab2 = st.tabs(["성적 입력", "성적 조회/그래프"])

    with tab1:
        if not students:
            st.info("학생이 없습니다.")
        else:
            s_opts = {
                f"{name} ({grade}, {school})": sid
                for sid, name, school, grade, phone, memo in students
            }
            s_label = st.selectbox(
                "학생 선택", list(s_opts.keys()), key="as_student"
            )
            student_id = s_opts[s_label]

            c_id = None
            if classes:
                c_opts = {"(선택 안함)": None}
                c_opts.update(
                    {
                        f"{name} ({level})": cid
                        for cid, name, level, memo in classes
                    }
                )
                c_label = st.selectbox(
                    "반 선택(선택)",
                    list(c_opts.keys()),
                    key="as_class",
                )
                c_id = c_opts[c_label]

            d = st.date_input("일자", value=date.today(), key="as_date")
            subject_options = get_common_subjects()
            if subject_options:
                subject_choice = st.selectbox(
                    "과목 선택",
                    ["(직접 입력)"] + subject_options,
                    key="as_subject_choice",
                )
                if subject_choice == "(직접 입력)":
                    subject = st.text_input(
                        "과목 (직접 입력)",
                        key="as_subject_manual",
                    )
                else:
                    subject = subject_choice
            else:
                subject = st.text_input("과목", key="as_subject_manual")
            test_name = st.text_input(
                "시험명 (예: 주간테스트)", key="as_test_name"
            )
            score = st.number_input(
                "점수", min_value=0.0, max_value=200.0,
                value=0.0, key="as_score",
            )
            max_score = st.number_input(
                "만점", min_value=0.0, max_value=200.0,
                value=100.0, key="as_max_score",
            )
            memo = st.text_area("메모", key="as_memo")

            if st.button("학원 성적 저장"):
                if not subject.strip():
                    st.warning("과목은 필수입니다.")
                else:
                    add_academy_score(
                        student_id,
                        c_id,
                        d.strftime("%Y-%m-%d"),
                        subject.strip(),
                        test_name.strip(),
                        score,
                        max_score,
                        memo.strip(),
                        user["id"],
                    )
                    st.success("학원 성적이 저장되었습니다.")

    with tab2:
        if not students:
            st.info("학생이 없습니다.")
        else:
            s_opts = {
                f"{name} ({grade}, {school})": sid
                for sid, name, school, grade, phone, memo in students
            }
            s_label = st.selectbox(
                "조회할 학생",
                list(s_opts.keys()),
                key="asv_student",
            )
            student_id = s_opts[s_label]
            subject = st.text_input(
                "과목 필터 (비우면 전체)",
                key="asv_subject",
            ).strip()
            subject_filter = subject if subject else None

            rows = get_scores_for_student(
                "academy_scores", student_id, subject_filter
            )
            if not rows:
                st.info("성적 기록이 없습니다.")
            else:
                data = []
                for dt, subj, test_name, score, max_score in rows:
                    data.append(
                        {
                            "날짜": dt,
                            "과목": subj,
                            "시험명": test_name,
                            "점수": score,
                            "만점": max_score,
                        }
                    )
                df = pd.DataFrame(data)
                st.dataframe(df, use_container_width=True)

                df_plot = df.copy()
                df_plot["날짜"] = pd.to_datetime(df_plot["날짜"])
                df_plot.set_index("날짜", inplace=True)
                st.line_chart(df_plot["점수"])


def admin_timetable():
    st.markdown("### 🗓 시간표 관리")
    classes = get_classes()
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]

    tab1, tab2 = st.tabs(["시간표 입력", "시간표 보기 (요일별 그리드)"])

    # 시간표 입력
    with tab1:
        if not classes:
            st.info("반이 없습니다.")
        else:
            c_opts = {
                f"{name} ({level})": cid
                for cid, name, level, memo in classes
            }
            c_label = st.selectbox(
                "반 선택", list(c_opts.keys()), key="tt_class"
            )
            class_id = c_opts[c_label]

            weekday_label = st.selectbox(
                "요일", weekdays, key="tt_weekday"
            )
            weekday_idx = weekdays.index(weekday_label)

            st_time = st.time_input(
                "시작 시간", value=time(18, 0), key="tt_start"
            )
            en_time = st.time_input(
                "종료 시간", value=time(20, 0), key="tt_end"
            )

            subject = st.text_input("과목", key="tt_subject")
            room = st.text_input("강의실", key="tt_room")
            teacher_name = st.text_input(
                "담당 선생님", key="tt_teacher"
            )
            memo = st.text_area("메모", key="tt_memo")

            if st.button("시간표 추가"):
                if not subject.strip():
                    st.warning("과목은 필수입니다.")
                else:
                    add_timetable(
                        class_id,
                        weekday_idx,
                        st_time.strftime("%H:%M"),
                        en_time.strftime("%H:%M"),
                        subject.strip(),
                        room.strip(),
                        teacher_name.strip(),
                        memo.strip(),
                    )
                    st.success("시간표가 추가되었습니다.")

    # 시간표 보기
       # 시간표 보기
    with tab2:
        if not classes:
            st.info("반이 없습니다.")
        else:
            c_opts = {
                f"{name} ({level})": cid
                for cid, name, level, memo in classes
            }
            c_label = st.selectbox(
                "반 선택", list(c_opts.keys()), key="ttv_class"
            )
            class_id = c_opts[c_label]

            rows = get_timetables_for_classes([class_id])
            if not rows:
                st.info("시간표가 없습니다.")
            else:
                weekdays = ["월", "화", "수", "목", "금", "토", "일"]
                data = []
                for (tid, cname, weekday, st_time_str, en_time_str,
                     subj, room, teacher, memo, class_id_in_row) in rows:  # ← 10개
                    data.append(
                        {
                            "요일": weekdays[weekday],
                            "시작": st_time_str,
                            "종료": en_time_str,
                            "과목": subj,
                            "강의실": room,
                            "선생님": teacher,
                            "메모": memo,
                        }
                    )
                df = pd.DataFrame(data)
                st.dataframe(df, use_container_width=True)

def admin_attendance_management():
    st.markdown("### 🕒 출석 / 과제 / 일일테스트 관리")
    user = st.session_state["user"]
    students = get_students()
    classes = get_classes()

    tab1, tab2, tab3 = st.tabs(
        ["출석/과제/테스트 입력 (QR/수동)", "일별 현황 한눈에 보기", "월별 캘린더 보기"]
    )

    # ----------------- 탭1: 입력 -----------------
    with tab1:
        # 출석 입력 날짜
        att_date = st.date_input(
            "출석 기록 날짜",
            value=date.today(),
            key="att_date_input",
        )
        att_date_str = att_date.strftime("%Y-%m-%d")

        if not students:
            st.info("학생이 없습니다.")
        else:
            # ===== 1) 개별 입력 (QR/수동) =====
            st.markdown("#### 개별 입력 (QR / 수동)")

            # QR/ID 입력
            code = st.text_input(
                "QR 코드값 / 학생 ID",
                placeholder="QR 스캐너 또는 학생 ID 직접 입력",
                key="att_single_code",
            )

            # ID → 학생 매핑
            student_map_by_id = {
                str(sid): (sid, name, school, grade, phone, memo)
                for sid, name, school, grade, phone, memo in students
            }

            # 수동 학생 선택
            manual_opts = {
                f"{name} ({grade}, {school})": sid
                for sid, name, school, grade, phone, memo in students
            }
            manual_label = st.selectbox(
                "수동 학생 선택",
                ["(선택 안 함)"] + list(manual_opts.keys()),
                key="att_single_manual_student",
            )

            # 반 선택 (선택사항)
            class_id = None
            if classes:
                class_opts = {"(선택 안 함)": None}
                class_opts.update(
                    {
                        f"{name} ({level})": cid
                        for cid, name, level, memo in classes
                    }
                )
                class_label = st.selectbox(
                    "출석 반 (선택)",
                    list(class_opts.keys()),
                    key="att_single_class",
                )
                class_id = class_opts[class_label]

            # 출결 / 과제 / 일일 테스트 상태 선택
            status = st.selectbox(
                "출결 상태",
                ["정상출석", "지각", "미인정결석"],
                key="att_single_status",
            )
            homework_status = st.selectbox(
                "과제",
                ["○", "△", "X"],
                index=0,
                key="att_single_hw",
            )
            daily_test_status = st.selectbox(
                "일일 테스트",
                ["○", "△", "X"],
                index=0,
                key="att_single_test",
            )

            via = "QR" if code.strip() else "수동"

            if st.button(
                "저장 (개별 출결 + 과제 + 일일테스트)",
                key="att_single_save",
            ):
                target_student_id = None
                target_student_name = None

                # 1순위: QR/ID 입력
                if code.strip():
                    if code.strip() in student_map_by_id:
                        rec = student_map_by_id[code.strip()]
                        target_student_id = rec[0]
                        target_student_name = rec[1]
                    else:
                        st.error("QR/ID에 해당하는 학생을 찾을 수 없습니다.")
                # 2순위: 수동 선택
                elif manual_label != "(선택 안 함)":
                    target_student_id = manual_opts[manual_label]
                    target_student_name = manual_label.split(" (")[0]
                else:
                    st.error("학생을 선택하거나 QR/ID를 입력하세요.")

                if target_student_id is not None:
                    add_attendance(
                        student_id=target_student_id,
                        class_id=class_id,
                        status=status,
                        homework_status=homework_status,
                        daily_test_status=daily_test_status,
                        via=via,
                        recorded_by=user["id"],
                        date_str=att_date_str,
                    )
                    st.success(
                        f"{target_student_name} - "
                        f"[출결:{status}] [과제:{homework_status}] "
                        f"[테스트:{daily_test_status}] 저장 완료 ({via})"
                    )

            st.caption("※ QR 코드에는 현재 '학생 ID'를 인코딩해서 사용한다고 가정한다.")

            st.markdown("---")

            # ===== 2) 반 단위 일괄 입력 =====
            st.markdown("#### 반 단위 일괄 입력")

            if not classes:
                st.info("반이 없습니다. 먼저 반을 생성하세요.")
            else:
                bulk_class_opts = {
                    f"{name} ({level})": cid
                    for cid, name, level, memo in classes
                }
                bulk_class_label = st.selectbox(
                    "일괄 입력할 반 선택",
                    list(bulk_class_opts.keys()),
                    key="att_bulk_class_select",
                )
                bulk_class_id = bulk_class_opts[bulk_class_label]

                bulk_status = st.selectbox(
                    "반 전체 출결 상태",
                    ["정상출석", "지각", "미인정결석"],
                    key="att_bulk_status",
                )
                bulk_hw = st.selectbox(
                    "반 전체 과제 상태",
                    ["○", "△", "X"],
                    key="att_bulk_hw",
                )
                bulk_test = st.selectbox(
                    "반 전체 일일 테스트 상태",
                    ["○", "△", "X"],
                    key="att_bulk_test",
                )

                if st.button(
                    "반 전체 동일 값 저장",
                    key="att_bulk_save",
                ):
                    conn = get_connection()
                    cur = conn.cursor()
                    cur.execute(
                        """
                        SELECT s.id, s.name, s.school, s.grade
                        FROM class_students cs
                        JOIN students s ON cs.student_id = s.id
                        WHERE cs.class_id=?
                        ORDER BY s.name
                        """,
                        (bulk_class_id,),
                    )
                    class_students = cur.fetchall()
                    conn.close()

                    if not class_students:
                        st.warning("해당 반에 학생이 없습니다.")
                    else:
                        for sid, name, school, grade in class_students:
                            add_attendance(
                                student_id=sid,
                                class_id=bulk_class_id,
                                status=bulk_status,
                                homework_status=bulk_hw,
                                daily_test_status=bulk_test,
                                via="반일괄",
                                recorded_by=user["id"],
                                date_str=att_date_str,
                            )
                        st.success(
                            f"{bulk_class_label} 학생 전원에게 "
                            f"[출결:{bulk_status}] [과제:{bulk_hw}] "
                            f"[테스트:{bulk_test}]로 저장되었습니다."
                        )

    # ----------------- 탭2: 일별 현황 -----------------
    with tab2:
        st.markdown("#### 일별 출결/과제/일일테스트 현황")

        date_value = st.date_input("조회 날짜", value=date.today())
        date_str = date_value.strftime("%Y-%m-%d")

        class_id_filter = None
        if classes:
            class_opts = ["(전체)"] + [
                f"{name} ({level})" for cid, name, level, memo in classes
            ]
            class_map = {
                f"{name} ({level})": cid
                for cid, name, level, memo in classes
            }
            class_label = st.selectbox("반 필터", class_opts)
            if class_label != "(전체)":
                class_id_filter = class_map[class_label]

        records = get_attendance_records(date_str, class_id_filter)
        if not records:
            st.info("해당 날짜에 출결 기록이 없습니다.")
        else:
            data = []
            for (aid, dt, time_str, status, hw, test, via,
                 s_name, school, grade, class_name) in records:
                data.append(
                    {
                        "시간": time_str,
                        "학생": s_name,
                        "학교": school,
                        "학년": grade,
                        "반": class_name,
                        "출결": status,
                        "과제": hw or "",
                        "일일테스트": test or "",
                        "입력경로": via,
                    }
                )
            df = pd.DataFrame(data)

            st.markdown("##### 상세 목록 (색상으로 직관적 표시)")

            def color_cell(val):
                if val == "정상출석":
                    return "background-color:#2f855a; color:white"
                if val == "지각":
                    return "background-color:#d69e2e; color:white"
                if val == "미인정결석":
                    return "background-color:#c53030; color:white"
                if val == "○":
                    return "background-color:#2f855a; color:white"
                if val == "△":
                    return "background-color:#d69e2e; color:white"
                if val == "X":
                    return "background-color:#c53030; color:white"
                return ""

            styled = df.style.applymap(
                color_cell, subset=["출결", "과제", "일일테스트"]
            )
            st.dataframe(styled, use_container_width=True)

            st.markdown("##### 요약")

            att_counts = df["출결"].value_counts()
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("정상출석", int(att_counts.get("정상출석", 0)))
            with c2:
                st.metric("지각", int(att_counts.get("지각", 0)))
            with c3:
                st.metric("미인정결석", int(att_counts.get("미인정결석", 0)))

            hw_counts = df["과제"].value_counts()
            t1, t2, t3 = st.columns(3)
            with t1:
                st.metric("과제 ○ (완료)", int(hw_counts.get("○", 0)))
            with t2:
                st.metric("과제 △ (부분)", int(hw_counts.get("△", 0)))
            with t3:
                st.metric("과제 X (미제출)", int(hw_counts.get("X", 0)))

            test_counts = df["일일테스트"].value_counts()
            u1, u2, u3 = st.columns(3)
            with u1:
                st.metric("테스트 ○ (정상)", int(test_counts.get("○", 0)))
            with u2:
                st.metric("테스트 △ (애매)", int(test_counts.get("△", 0)))
            with u3:
                st.metric("테스트 X (미응시)", int(test_counts.get("X", 0)))

    # ----------------- 탭3: 월별 캘린더 -----------------
    with tab3:
        st.markdown("#### 월별 출석 캘린더")

        base_date = st.date_input(
            "조회할 월 선택 (임의의 날짜 선택하면 해당 월 전체를 봄)",
            value=date.today(),
            key="att_cal_base",
        )
        year = base_date.year
        month = base_date.month

        class_id_filter = None
        if classes:
            class_opts = ["(전체)"] + [
                f"{name} ({level})" for cid, name, level, memo in classes
            ]
            class_map = {
                f"{name} ({level})": cid
                for cid, name, level, memo in classes
            }
            class_label = st.selectbox(
                "반 필터 (월 전체에 적용)",
                class_opts,
                key="att_cal_class",
            )
            if class_label != "(전체)":
                class_id_filter = class_map[class_label]

        import calendar
        first_day = date(year, month, 1)
        last_day_num = calendar.monthrange(year, month)[1]

        # 날짜별 출석 요약 계산
        daily_summary = {}
        for day in range(1, last_day_num + 1):
            d = date(year, month, day)
            d_str = d.strftime("%Y-%m-%d")
            recs = get_attendance_records(d_str, class_id_filter)
            if not recs:
                daily_summary[day] = None
            else:
                normal = sum(1 for r in recs if r[3] == "정상출석")
                late = sum(1 for r in recs if r[3] == "지각")
                absent = sum(1 for r in recs if r[3] == "미인정결석")
                daily_summary[day] = (normal, late, absent)

        # 캘린더 테이블 구성 (6주 * 7일)
        weekdays = ["월", "화", "수", "목", "금", "토", "일"]
        cal_matrix = [[ "" for _ in range(7)] for _ in range(6)]

        first_wday = (first_day.weekday())  # 월=0
        week_idx = 0
        col_idx = first_wday

        for day in range(1, last_day_num + 1):
            summary = daily_summary[day]
            if summary is None:
                cell = f"{day}"
            else:
                n, l, a = summary
                cell = f"{day}\n정:{n} 지:{l} 결:{a}"
            cal_matrix[week_idx][col_idx] = cell

            col_idx += 1
            if col_idx >= 7:
                col_idx = 0
                week_idx += 1

        df_cal = pd.DataFrame(cal_matrix, columns=weekdays)
        st.dataframe(df_cal, use_container_width=True)
        st.caption("각 셀: '일자 / 정상출석 수 / 지각 수 / 미인정결석 수'")


def admin_vocab_management():
    st.markdown("### 📘 단어장 관리")
    user = st.session_state["user"]
    vocab_sets = get_vocab_sets(active_only=False)
    classes = get_classes()
    students = get_students()

    tab1, tab2, tab3, tab4 = st.tabs(
        ["세트 관리", "단어 일괄 입력(엑셀/한글)", "배포(할당)", "결과 요약"]
    )

    # ================== 세트 관리 ==================
    with tab1:
        with st.form("vs_create"):
            name = st.text_input("단어장 이름 (예: 중2A 3월 단어)")
            desc = st.text_area("설명")
            level = st.text_input("레벨/학년 (예: 중2)")
            submitted = st.form_submit_button("단어장 세트 생성")
            if submitted:
                if not name.strip():
                    st.warning("이름은 필수입니다.")
                else:
                    create_vocab_set(
                        name.strip(),
                        desc.strip(),
                        level.strip(),
                        user["id"],
                    )
                    st.success("단어장 세트가 생성되었습니다.")

        st.markdown("#### 단어장 세트 목록")
        if not vocab_sets:
            st.info("단어장 세트가 없습니다.")
        else:
            data = []
            for sid, name, desc, level, cb, ca, act in vocab_sets:
                data.append(
                    {
                        "ID": sid,
                        "이름": name,
                        "설명": desc,
                        "레벨": level,
                        "활성": "Y" if act else "N",
                        "생성시각": ca,
                    }
                )
            st.dataframe(pd.DataFrame(data), use_container_width=True)

    # ================== 단어 일괄 입력(엑셀/한글) ==================
    with tab2:
        active_sets = get_vocab_sets(active_only=False)
        if not active_sets:
            st.info("먼저 단어장 세트를 생성하세요.")
        else:
            set_opts = {
                f"{name} ({level})": sid
                for sid, name, desc, level, cb, ca, act in active_sets
            }
            set_label = st.selectbox(
                "단어를 넣을 단어장 세트 선택",
                list(set_opts.keys()),
                key="vocab_bulk_set",
            )
            set_id = set_opts[set_label]

            st.markdown("#### 엑셀 / 한글에서 복사해서 붙여넣기")

            st.caption(
                """
                **입력 형식 (권장: 탭 구분)**  
                - 최소: `단어[TAB]뜻`  
                - 확장: `단어[TAB]뜻[TAB]품사[TAB]예문(영)[TAB]예문(한)[TAB]태그[TAB]난이도(1~5)`  
                - 예시  
                  - `abandon[TAB]버리다`  
                  - `abandon[TAB]버리다[TAB]v.[TAB]He abandoned the plan.[TAB]그는 계획을 버렸다.[TAB]수능,필수[TAB]3`  
                - 탭이 없고 `단어 / 뜻` 형식이면 자동 인식 (예: `abandon / 버리다`)
                """
            )

            raw_text = st.text_area(
                "엑셀/한글에서 그대로 붙여넣으세요.",
                height=200,
                key="vocab_bulk_text",
            )

            if st.button("단어 대량 추가 (Parse & Save)"):
                lines = [l.rstrip() for l in raw_text.split("\n") if l.strip()]
                if not lines:
                    st.warning("유효한 줄이 없습니다.")
                else:
                    parsed_rows = []
                    for line in lines:
                        # 1순위: 탭 구분 (엑셀)
                        if "\t" in line:
                            cols = [c.strip() for c in line.split("\t")]
                        # 2순위: `/` 구분 백업
                        elif "/" in line:
                            w, m = line.split("/", 1)
                            cols = [w.strip(), m.strip()]
                        else:
                            # 인식 불가 → 스킵
                            continue

                        if len(cols) < 2:
                            continue

                        word = cols[0]
                        meaning = cols[1]
                        pos = cols[2] if len(cols) >= 3 else ""
                        ex_en = cols[3] if len(cols) >= 4 else ""
                        ex_ko = cols[4] if len(cols) >= 5 else ""
                        tags = cols[5] if len(cols) >= 6 else ""
                        # 난이도
                        if len(cols) >= 7:
                            try:
                                diff = int(cols[6])
                                if diff < 1 or diff > 5:
                                    diff = 3
                            except ValueError:
                                diff = 3
                        else:
                            diff = 3

                        if word and meaning:
                            parsed_rows.append(
                                (word, meaning, pos, ex_en, ex_ko, tags, diff)
                            )

                    if not parsed_rows:
                        st.error("파싱에 성공한 라인이 없습니다. 탭 또는 ' / ' 구분을 확인하세요.")
                    else:
                        # DB 저장
                        for (w, m, pos, ex_en, ex_ko, tags, diff) in parsed_rows:
                            add_vocab_item(
                                set_id,
                                w,
                                m,
                                pos,
                                ex_en,
                                ex_ko,
                                tags,
                                diff,
                            )

                        st.success(f"{len(parsed_rows)}개 단어가 추가되었습니다.")

                        # 미리보기
                        st.markdown("#### 추가된 데이터 미리보기")
                        preview_data = []
                        for (w, m, pos, ex_en, ex_ko, tags, diff) in parsed_rows[:50]:
                            preview_data.append(
                                {
                                    "단어": w,
                                    "뜻": m,
                                    "품사": pos,
                                    "예문(영)": ex_en,
                                    "예문(한)": ex_ko,
                                    "태그": tags,
                                    "난이도": diff,
                                }
                            )
                        st.dataframe(pd.DataFrame(preview_data), use_container_width=True)

            st.markdown("#### 현재 세트 단어 목록")
            items = get_vocab_items(set_id)
            if not items:
                st.info("등록된 단어가 없습니다.")
            else:
                data = []
                for vid, w, m, pos, ex_en, ex_ko, tags, diff in items:
                    data.append(
                        {
                            "ID": vid,
                            "단어": w,
                            "뜻": m,
                            "품사": pos,
                            "태그": tags,
                            "난이도": diff,
                        }
                    )
                st.dataframe(pd.DataFrame(data), use_container_width=True)

    # ================== 배포(할당) ==================
    with tab3:
        if not vocab_sets:
            st.info("단어장 세트가 없습니다.")
        else:
            set_opts = {
                f"{name} ({level})": sid
                for sid, name, desc, level, cb, ca, act in vocab_sets
            }
            set_label = st.selectbox(
                "단어장 세트 선택",
                list(set_opts.keys()),
                key="va_set",
            )
            set_id = set_opts[set_label]

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("##### 반 전체에 할당")
                if not classes:
                    st.info("반이 없습니다.")
                else:
                    c_opts = {
                        f"{name} ({level})": cid
                        for cid, name, level, memo in classes
                    }
                    c_label = st.selectbox(
                        "반 선택",
                        list(c_opts.keys()),
                        key="va_class",
                    )
                    class_id = c_opts[c_label]
                    if st.button("해당 반 전체에 할당"):
                        assign_vocab_to_class(
                            set_id, class_id, user["id"]
                        )
                        st.success("해당 반 전체에 단어장이 할당되었습니다.")

            with col2:
                st.markdown("##### 개별 학생에게 할당")
                if not students:
                    st.info("학생이 없습니다.")
                else:
                    s_opts = {
                        f"{name} ({grade}, {school})": sid
                        for sid, name, school, grade, phone, memo in students
                    }
                    s_label = st.selectbox(
                        "학생 선택",
                        list(s_opts.keys()),
                        key="va_student",
                    )
                    student_id = s_opts[s_label]
                    if st.button("해당 학생에게만 할당"):
                        assign_vocab_to_student(
                            set_id, student_id, user["id"]
                        )
                        st.success("해당 학생에게 단어장이 할당되었습니다.")

            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                """
                SELECT va.id, c.name, s.name, va.assigned_at
                FROM vocab_assignments va
                LEFT JOIN classes c ON va.class_id=c.id
                LEFT JOIN students s ON va.student_id=s.id
                WHERE va.set_id=?
                ORDER BY va.assigned_at DESC
                """,
                (set_id,),
            )
            rows = cur.fetchall()
            conn.close()

            st.markdown("#### 현재 세트 할당 현황")
            if not rows:
                st.info("아직 할당된 대상이 없습니다.")
            else:
                data = []
                for aid, cname, sname, at in rows:
                    target = cname if cname else sname
                    kind = "반" if cname else "학생"
                    data.append(
                        {
                            "ID": aid,
                            "대상 유형": kind,
                            "대상 이름": target,
                            "할당 시각": at,
                        }
                    )
                st.dataframe(pd.DataFrame(data), use_container_width=True)

    # ================== 결과 요약 ==================
    with tab4:
        if not vocab_sets:
            st.info("단어장 세트가 없습니다.")
        else:
            set_opts = {
                f"{name} ({level})": sid
                for sid, name, desc, level, cb, ca, act in vocab_sets
            }
            set_label = st.selectbox(
                "세트 선택", list(set_opts.keys()), key="vr_set"
            )
            set_id = set_opts[set_label]

            results = get_vocab_results_for_set(set_id)
            if not results:
                st.info("퀴즈 결과 기록이 없습니다.")
            else:
                data = []
                for (sid, sname, taken_at, correct,
                     total, percent) in results:
                    data.append(
                        {
                            "학생": sname,
                            "시각": taken_at,
                            "정답": correct,
                            "문항 수": total,
                            "정답률(%)": round(percent, 1),
                        }
                    )
                st.dataframe(pd.DataFrame(data), use_container_width=True)

def admin_dashboard():
    """관리자/마스터 로그인 시 처음 보게 될 메인 대시보드"""
    st.markdown("### 🏫 메인 대시보드")

    students = get_students()
    classes = get_classes()

    today = date.today()
    today_str = today.strftime("%Y-%m-%d")

    # ===== 상단 요약 지표 =====
    conn = get_connection()
    cur = conn.cursor()

    total_students = len(students)
    total_classes = len(classes)

    cur.execute("SELECT COUNT(*) FROM attendance WHERE date=?", (today_str,))
    today_att = cur.fetchone()[0] or 0

    cutoff_30 = (today - pd.Timedelta(days=30)).strftime("%Y-%m-%d")
    cur.execute("SELECT COUNT(*) FROM school_scores WHERE date>=?", (cutoff_30,))
    sc_30 = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM academy_scores WHERE date>=?", (cutoff_30,))
    ac_30 = cur.fetchone()[0] or 0

    conn.close()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("등록 학생 수", total_students)
    with c2:
        st.metric("등록 반 수", total_classes)
    with c3:
        st.metric("오늘 출결 기록 수", today_att)
    with c4:
        st.metric("최근 30일 성적 입력", sc_30 + ac_30)

    st.markdown("---")

    # ===== 반별 출결/진도 월간 캘린더 =====
    st.markdown("#### 📆 반별 출결/진도 캘린더")

    if not classes:
        st.info("반이 없습니다. 먼저 반을 생성하세요.")
    else:
        class_opts = {
            f"{name} ({level})" if level else name: cid
            for cid, name, level, memo in classes
        }
        sel_class_label = st.selectbox(
            "반 선택 (월간 출결 요약)",
            list(class_opts.keys()),
            key="dashboard_calendar_class",
        )
        sel_class_id = class_opts[sel_class_label]

        base_date = st.date_input(
            "기준 월 선택",
            value=today.replace(day=1),
            key="dashboard_calendar_month",
        )
        year = base_date.year
        month = base_date.month

        import calendar
        first_day = date(year, month, 1)
        last_day_num = calendar.monthrange(year, month)[1]

        start_str = f"{year:04d}-{month:02d}-01"
        end_str = f"{year:04d}-{month:02d}-{last_day_num:02d}"

        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT date, status, homework_status, daily_test_status
            FROM attendance
            WHERE class_id=? AND date BETWEEN ? AND ?
            """,
            (sel_class_id, start_str, end_str),
        )
        rows = cur.fetchall()
        conn.close()

        # 일자별 요약 상태 집계
        daily_status = {d: [] for d in range(1, last_day_num + 1)}
        for dt_str, status, hw, test in rows:
            try:
                day = int(dt_str[-2:])
            except ValueError:
                continue
            flags = [status or ""]
            if hw:
                flags.append(f"과제:{hw}")
            if test:
                flags.append(f"테스트:{test}")
            daily_status[day].append(" / ".join(flags))

        # 캘린더 매트릭스 구성
        weekdays = ["월", "화", "수", "목", "금", "토", "일"]
        cal_matrix = [["" for _ in range(7)] for _ in range(6)]

        first_weekday = first_day.weekday()  # 월=0
        week_idx = 0
        col_idx = first_weekday

        for d in range(1, last_day_num + 1):
            cell_text = str(d)
            flags = daily_status[d]

            # 색상용 상태 코드
            status_code = ""
            if flags:
                joined = " ".join(flags)
                if "미인정결석" in joined:
                    status_code = "결석"
                elif "지각" in joined or "X" in joined:
                    status_code = "주의"
                elif "정상출석" in joined:
                    status_code = "정상"

                cell_text += "\n" + status_code

            cal_matrix[week_idx][col_idx] = cell_text

            col_idx += 1
            if col_idx >= 7:
                col_idx = 0
                week_idx += 1
                if week_idx >= 6:
                    break

        df_cal = pd.DataFrame(cal_matrix, columns=weekdays)

        def _cal_color(val: str):
            if not isinstance(val, str):
                return ""
            if "결석" in val:
                return "background-color:#c53030; color:white"
            if "주의" in val:
                return "background-color:#d69e2e; color:white"
            if "정상" in val:
                return "background-color:#2f855a; color:white"
            return ""

        styled_cal = df_cal.style.applymap(_cal_color)
        st.dataframe(styled_cal, use_container_width=True)
        st.caption("· 빨강=결석 / 노랑=지각·과제·테스트 문제 / 초록=정상만 있는 날")

    st.markdown("---")

    # ===== 반/학생 빠른 조회 + '자세히 보기' =====
    st.markdown("#### 👤 반/학생 빠른 조회")

    if not classes or not students:
        st.info("학생 및 반 정보가 부족합니다. 먼저 학생과 반을 등록하세요.")
        return

    # 반 선택 → 해당 반 학생 목록
    class_opts2 = {
        f"{name} ({level})" if level else name: cid
        for cid, name, level, memo in classes
    }
    sel_class_label2 = st.selectbox(
        "조회할 반 선택",
        list(class_opts2.keys()),
        key="dashboard_quick_class",
    )
    sel_class_id2 = class_opts2[sel_class_label2]

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT s.id, s.name, s.school, s.grade
        FROM class_students cs
        JOIN students s ON cs.student_id = s.id
        WHERE cs.class_id=?
        ORDER BY s.name
        """,
        (sel_class_id2,),
    )
    class_students = cur.fetchall()
    conn.close()

    if not class_students:
        st.info("해당 반에 배정된 학생이 없습니다.")
        return

    student_label_map = {
        f"{name} ({grade}, {school})": sid
        for sid, name, school, grade in class_students
    }
    sel_student_label = st.selectbox(
        "학생 선택",
        list(student_label_map.keys()),
        key="dashboard_quick_student",
    )
    sel_student_id = student_label_map[sel_student_label]
    sel_student_name = sel_student_label.split(" (")[0]

    st.markdown(f"**선택된 학생:** `{sel_student_name}`")

    # ---------- 최근 출결 / 과제 / 일일테스트 ----------
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT date, status, homework_status, daily_test_status, checkin_time
        FROM attendance
        WHERE student_id=?
        ORDER BY date DESC, checkin_time DESC
        LIMIT 10
        """,
        (sel_student_id,),
    )
    att_rows = cur.fetchall()

    # ---------- 최근 진도 ----------
    cur.execute(
        """
        SELECT date, subject, unit, memo
        FROM academy_progress
        WHERE student_id=?
        ORDER BY date DESC
        LIMIT 10
        """,
        (sel_student_id,),
    )
    prog_rows = cur.fetchall()

    # ---------- 최근 성적 ----------
    school_scores = get_scores_for_student("school_scores", sel_student_id)
    academy_scores = get_scores_for_student("academy_scores", sel_student_id)
    recent_school = school_scores[-5:] if school_scores else []
    recent_academy = academy_scores[-5:] if academy_scores else []

    conn.close()

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("##### 🕒 최근 출결 / 과제 / 일일테스트")
        if not att_rows:
            st.info("출결 기록이 없습니다.")
        else:
            data = []
            for dt_str, status, hw, test, t_str in att_rows:
                data.append(
                    {
                        "날짜": dt_str,
                        "시간": t_str,
                        "출결": status,
                        "과제": hw or "",
                        "일일테스트": test or "",
                    }
                )
            st.dataframe(pd.DataFrame(data), use_container_width=True)
        if st.button("출결 자세히 보기", key="dash_att_detail"):
            # 수업 관리 페이지로 이동 (출결 탭에서 확인)
            st.session_state["admin_menu"] = "수업 관리"
            st.session_state["lesson_focus_student_id"] = sel_student_id
            st.session_state["lesson_focus_class_id"] = sel_class_id2
            st.rerun()

    with col2:
        st.markdown("##### 📚 최근 진도")
        if not prog_rows:
            st.info("진도 기록이 없습니다.")
        else:
            data = []
            for dt_str, subj, unit, memo in prog_rows:
                data.append(
                    {
                        "날짜": dt_str,
                        "과목": subj,
                        "단원/교재": unit,
                        "메모": memo,
                    }
                )
            st.dataframe(pd.DataFrame(data), use_container_width=True)
        if st.button("진도 자세히 보기", key="dash_prog_detail"):
            st.session_state["admin_menu"] = "수업 관리"
            st.session_state["lesson_focus_student_id"] = sel_student_id
            st.session_state["lesson_focus_class_id"] = sel_class_id2
            st.rerun()

    col3, col4 = st.columns(2)

    with col3:
        st.markdown("##### 🏫 최근 학교 성적")
        if not recent_school:
            st.info("학교 성적 기록이 없습니다.")
        else:
            data = []
            for dt, subj, exam_name, score, max_score in recent_school:
                data.append(
                    {
                        "날짜": dt,
                        "과목": subj,
                        "시험명": exam_name,
                        "점수": score,
                        "만점": max_score,
                    }
                )
            st.dataframe(pd.DataFrame(data), use_container_width=True)
        if st.button("학교 성적 자세히 보기", key="dash_school_detail"):
            st.session_state["admin_menu"] = "성적 관리"
            st.session_state["score_focus_student_id"] = sel_student_id
            st.session_state["score_focus_mode"] = "school"
            st.rerun()

    with col4:
        st.markdown("##### 📊 최근 학원 성적")
        if not recent_academy:
            st.info("학원 성적 기록이 없습니다.")
        else:
            data = []
            for dt, subj, test_name, score, max_score in recent_academy:
                data.append(
                    {
                        "날짜": dt,
                        "과목": subj,
                        "시험명": test_name,
                        "점수": score,
                        "만점": max_score,
                    }
                )
            st.dataframe(pd.DataFrame(data), use_container_width=True)
        if st.button("학원 성적 자세히 보기", key="dash_academy_detail"):
            st.session_state["admin_menu"] = "성적 관리"
            st.session_state["score_focus_student_id"] = sel_student_id
            st.session_state["score_focus_mode"] = "academy"
            st.rerun()

    st.markdown("##### 🗓 학생 시간표 (해당 반 기준)")
    timetable_rows = get_timetables_for_classes([sel_class_id2])
    if not timetable_rows:
        st.info("해당 반 시간표가 없습니다.")
    else:
        weekdays = ["월", "화", "수", "목", "금", "토", "일"]
        data = []
        for (
            tid,
            cname,
            weekday,
            st_time_str,
            en_time_str,
            subj,
            room,
            teacher,
            memo,
            class_id_row,
        ) in timetable_rows:
            data.append(
                {
                    "요일": weekdays[weekday],
                    "시작": st_time_str,
                    "종료": en_time_str,
                    "과목": subj,
                    "강의실": room,
                    "선생님": teacher,
                    "메모": memo,
                }
            )
        df_tt = pd.DataFrame(data)
        st.dataframe(df_tt, use_container_width=True)

    if st.button("시간표 자세히 보기", key="dash_tt_detail"):
        st.session_state["admin_menu"] = "시간표 관리"
        st.session_state["timetable_focus_class_id"] = sel_class_id2
        st.rerun()

    # ===== 리포트 카드 (월간) =====
    st.markdown("---")
    st.markdown("#### 📝 월간 리포트 카드 (인쇄용)")

    report_month = st.date_input(
        "리포트 기준 월 선택",
        value=today.replace(day=1),
        key="dashboard_report_month",
    )
    rep_year = report_month.year
    rep_month = report_month.month

    # ---------- (1) 월간 출결 캘린더 ----------
    st.markdown("##### 📆 월간 출결 캘린더")

    import calendar
    first_day = date(rep_year, rep_month, 1)
    last_day_num = calendar.monthrange(rep_year, rep_month)[1]

    att_month_rows = get_attendance_for_student_month(
        sel_student_id, rep_year, rep_month
    )

    # 일자별 상태 집계
    daily_status = {d: [] for d in range(1, last_day_num + 1)}
    for dt_str, status, hw, test in att_month_rows:
        try:
            day = int(dt_str[-2:])
        except ValueError:
            continue
        flags = []
        if status:
            flags.append(status)
        if hw:
            flags.append(f"과제:{hw}")
        if test:
            flags.append(f"테스트:{test}")
        daily_status[day].append(" / ".join(flags))

    # 6x7 매트릭스
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    cal_matrix = [["" for _ in range(7)] for _ in range(6)]

    first_weekday = first_day.weekday()  # 월=0
    week_idx = 0
    col_idx = first_weekday

    for d in range(1, last_day_num + 1):
        cell_text = str(d)
        flags = daily_status[d]

        status_code = ""
        joined = " ".join(flags)
        if "미인정결석" in joined:
            status_code = "결석"
        elif "지각" in joined or "X" in joined:
            status_code = "주의"
        elif "정상출석" in joined:
            status_code = "정상"

        if status_code:
            cell_text += f"\n{status_code}"

        cal_matrix[week_idx][col_idx] = cell_text

        col_idx += 1
        if col_idx >= 7:
            col_idx = 0
            week_idx += 1
            if week_idx >= 6:
                break

    df_month_cal = pd.DataFrame(cal_matrix, columns=weekdays)

    def _month_cal_color(val: str):
        if not isinstance(val, str):
            return ""
        if "결석" in val:
            return "background-color:#c53030; color:white"
        if "주의" in val:
            return "background-color:#d69e2e; color:white"
        if "정상" in val:
            return "background-color:#2f855a; color:white"
        return ""

    styled_month_cal = df_month_cal.style.applymap(_month_cal_color)
    st.dataframe(styled_month_cal, use_container_width=True)
    st.caption("· 빨강=결석 / 노랑=지각·과제·테스트 문제 / 초록=정상만 있는 날")

    # ---------- (2) 월간 성적 그래프 ----------
    st.markdown("##### 📈 월간 성적 요약 (그래프 + 표)")

    # school_scores / academy_scores는 함수 위쪽에서 이미 가져온 상태라고 가정
    def _filter_scores_by_month(rows, year, month):
        filtered = []
        for dt, subj, name, score, max_score in rows:
            try:
                y, m, _ = dt.split("-")
                if int(y) == year and int(m) == month:
                    filtered.append((dt, subj, name, score, max_score))
            except Exception:
                continue
        return filtered

    month_school = _filter_scores_by_month(
        school_scores or [], rep_year, rep_month
    )
    month_academy = _filter_scores_by_month(
        academy_scores or [], rep_year, rep_month
    )

    col_rs, col_ra = st.columns(2)

    with col_rs:
        st.markdown("###### 🏫 학교 성적")
        if not month_school:
            st.info("해당 월 학교 성적 기록이 없습니다.")
        else:
            data_sc = []
            for dt, subj, name, score, max_score in month_school:
                data_sc.append(
                    {
                        "날짜": dt,
                        "과목": subj,
                        "시험명": name,
                        "점수": score,
                        "만점": max_score,
                    }
                )
            df_sc = pd.DataFrame(data_sc)
            st.dataframe(df_sc, use_container_width=True)

            df_sc_plot = df_sc.copy()
            df_sc_plot["날짜"] = pd.to_datetime(df_sc_plot["날짜"])
            df_sc_plot.set_index("날짜", inplace=True)
            st.line_chart(df_sc_plot["점수"])

    with col_ra:
        st.markdown("###### 📊 학원 성적")
        if not month_academy:
            st.info("해당 월 학원 성적 기록이 없습니다.")
        else:
            data_ac = []
            for dt, subj, name, score, max_score in month_academy:
                data_ac.append(
                    {
                        "날짜": dt,
                        "과목": subj,
                        "시험명": name,
                        "점수": score,
                        "만점": max_score,
                    }
                )
            df_ac = pd.DataFrame(data_ac)
            st.dataframe(df_ac, use_container_width=True)

            df_ac_plot = df_ac.copy()
            df_ac_plot["날짜"] = pd.to_datetime(df_ac_plot["날짜"])
            df_ac_plot.set_index("날짜", inplace=True)
            st.line_chart(df_ac_plot["점수"])

    st.caption(
        "※ 리포트 카드는 이 화면에서 바로 브라우저 인쇄(Ctrl+P / Command+P)로 출력하거나 PDF로 저장할 수 있습니다."
    )

def admin_notice_management():
    st.markdown("### 📢 공지 관리")
    user = st.session_state["user"]

    tab1, tab2 = st.tabs(["공지 작성", "공지 목록"])

    with tab1:
        with st.form("notice_form"):
            title = st.text_input("제목 *")
            content = st.text_area("내용 *", height=200)
            pinned = st.checkbox("상단 고정")

            submitted = st.form_submit_button("등록")
            if submitted:
                if not title.strip() or not content.strip():
                    st.warning("제목과 내용을 모두 입력하세요.")
                else:
                    add_notice(title.strip(), content.strip(), pinned, user["id"])
                    st.success("공지가 등록되었습니다.")

    with tab2:
        notices = get_notices()
        if not notices:
            st.info("등록된 공지가 없습니다.")
        else:
            for nid, title, content, pinned, created_at in notices:
                header = f"📌 {title}" if pinned else title
                with st.expander(header):
                    st.markdown(f"*작성 시각: {created_at}*")
                    st.write(content)
                    if st.button("삭제", key=f"notice_del_{nid}"):
                        delete_notice(nid)
                        st.warning("삭제되었습니다.")
                        st.rerun()


def master_admin_approval():
    st.markdown("### 🛠 관리자 승인 / 계정 관리 (마스터 전용)")

    user = st.session_state["user"]
    if user["role"] != "master":
        st.error("이 화면은 마스터만 접근할 수 있습니다.")
        return

    # -------- 1) 관리자 승인 대기 --------
    st.markdown("#### 관리자 승인 대기 목록")
    waiting_admins = get_waiting_admins()
    if not waiting_admins:
        st.info("승인 대기 중인 관리자가 없습니다.")
    else:
        for uid, username in waiting_admins:
            cols = st.columns([3, 1, 1])
            cols[0].markdown(f"- `{username}` (ID: {uid})")
            if cols[1].button("승인", key=f"approve_admin_{uid}"):
                approve_admin(uid, True)
                st.success(f"{username} 승인 완료")
                st.rerun()
            if cols[2].button("거절", key=f"reject_admin_{uid}"):
                approve_admin(uid, False)
                st.warning(f"{username} 거절 처리")
                st.rerun()

    st.markdown("---")

    # -------- 2) 학생 계정 승인 대기 --------
    st.markdown("#### 학생 계정 승인 대기 목록")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, username, student_id
        FROM users
        WHERE role='student' AND is_approved=0
        """
    )
    waiting_students = cur.fetchall()
    conn.close()

    if not waiting_students:
        st.info("승인 대기 중인 학생 계정이 없습니다.")
    else:
        students = get_students()
        stu_map = {sid: name for sid, name, school, grade, phone, memo in students}
        for uid, username, student_id in waiting_students:
            stu_name = stu_map.get(student_id, "미배정")
            cols = st.columns([4, 1, 1])
            cols[0].markdown(
                f"- `{username}` → 학생: **{stu_name}** (student_id: {student_id})"
            )
            if cols[1].button("승인", key=f"approve_stu_{uid}"):
                approve_admin(uid, True)  # is_approved만 1로 변경
                st.success(f"{username} 학생 계정 승인 완료")
                st.rerun()
            if cols[2].button("거절", key=f"reject_stu_{uid}"):
                approve_admin(uid, False)
                st.warning(f"{username} 학생 계정 거절 처리")
                st.rerun()

    st.markdown("---")

    # -------- 3) 전체 계정 활성/정지 --------
    st.markdown("#### 👥 전체 계정 활성/정지 관리")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, username, role, is_approved, is_active
        FROM users
        WHERE role != 'master'
        ORDER BY role, username
        """
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        st.info("관리 대상 계정이 없습니다. (현재 마스터 계정만 존재)")
    else:
        for uid, username, role, is_approved, is_active in rows:
            c1, c2, c3 = st.columns([4, 1, 1])
            status_text = "활성" if is_active else "정지"
            approved_text = "승인" if is_approved else "미승인"
            c1.write(
                f"`{username}` ({role}) - 승인: **{approved_text}** / 상태: **{status_text}**"
            )
            if c2.button("활성화", key=f"user_on_{uid}"):
                set_user_active(uid, True)
                st.success(f"{username} 계정을 활성화했습니다.")
                st.rerun()
            if c3.button("정지", key=f"user_off_{uid}"):
                set_user_active(uid, False)
                st.warning(f"{username} 계정을 정지했습니다.")
                st.rerun()

def admin_data_management():
    st.markdown("### 🗂 데이터 관리 (마스터 전용)")

    user = st.session_state["user"]
    if user["role"] != "master":
        st.error("이 화면은 마스터만 접근할 수 있습니다.")
        return

    mode = st.selectbox(
        "데이터 종류 선택",
        ["학교 성적", "학원 성적", "학원 진도", "출석"],
        key="data_manage_mode",
    )

    # =============== 학교 성적 관리 ===============
    if mode == "학교 성적":
        students = get_students()
        if not students:
            st.info("학생이 없습니다.")
            return

        s_opts = {
            f"{name} ({grade}, {school})": sid
            for sid, name, school, grade, phone, memo in students
        }
        s_label = st.selectbox(
            "학생 선택",
            list(s_opts.keys()),
            key="dm_school_student",
        )
        student_id = s_opts[s_label]

        subject = st.text_input(
            "과목 필터 (비우면 전체)",
            key="dm_school_subject",
        ).strip()
        subject_filter = subject if subject else None

        # id까지 포함해서 직접 조회
        conn = get_connection()
        cur = conn.cursor()
        query = """
            SELECT sc.id, sc.date, sc.subject, sc.exam_name,
                   sc.score, sc.max_score, sc.memo
            FROM school_scores sc
            WHERE sc.student_id=?
        """
        params = [student_id]
        if subject_filter:
            query += " AND sc.subject=?"
            params.append(subject_filter)
        query += " ORDER BY sc.date DESC, sc.id DESC"
        cur.execute(query, params)
        rows = cur.fetchall()
        conn.close()

        if not rows:
            st.info("해당 조건의 학교 성적이 없습니다.")
            return

        for sid, dt, subj, exam_name, score, max_score, memo in rows:
            with st.expander(f"{dt} • {subj} • {exam_name} • {score}/{max_score}"):
                # 날짜 문자열 -> date 객체
                try:
                    d_val = datetime.strptime(dt, "%Y-%m-%d").date()
                except Exception:
                    d_val = date.today()

                with st.form(f"dm_school_form_{sid}"):
                    d_input = st.date_input("날짜", value=d_val, key=f"dm_school_date_{sid}")
                    subj_input = st.text_input("과목", value=subj, key=f"dm_school_subj_{sid}")
                    exam_input = st.text_input("시험명", value=exam_name, key=f"dm_school_exam_{sid}")
                    score_input = st.number_input(
                        "점수",
                        min_value=0.0, max_value=200.0,
                        value=float(score) if score is not None else 0.0,
                        key=f"dm_school_score_{sid}",
                    )
                    max_input = st.number_input(
                        "만점",
                        min_value=0.0, max_value=200.0,
                        value=float(max_score) if max_score is not None else 100.0,
                        key=f"dm_school_max_{sid}",
                    )
                    memo_input = st.text_area(
                        "메모",
                        value=memo or "",
                        key=f"dm_school_memo_{sid}",
                    )

                    c1, c2 = st.columns(2)
                    with c1:
                        save_btn = st.form_submit_button("💾 수정 저장")
                    with c2:
                        del_btn = st.form_submit_button("🗑 삭제")

                    if save_btn:
                        update_school_score(
                            sid,
                            d_input.strftime("%Y-%m-%d"),
                            subj_input.strip(),
                            exam_input.strip(),
                            score_input,
                            max_input,
                            memo_input.strip(),
                        )
                        st.success("수정 완료")
                        st.rerun()
                    if del_btn:
                        delete_school_score(sid)
                        st.warning("삭제 완료")
                        st.rerun()

    # =============== 학원 성적 관리 ===============
    elif mode == "학원 성적":
        students = get_students()
        if not students:
            st.info("학생이 없습니다.")
            return

        s_opts = {
            f"{name} ({grade}, {school})": sid
            for sid, name, school, grade, phone, memo in students
        }
        s_label = st.selectbox(
            "학생 선택",
            list(s_opts.keys()),
            key="dm_academy_score_student",
        )
        student_id = s_opts[s_label]

        subject = st.text_input(
            "과목 필터 (비우면 전체)",
            key="dm_academy_score_subject",
        ).strip()
        subject_filter = subject if subject else None

        conn = get_connection()
        cur = conn.cursor()
        query = """
            SELECT ac.id, ac.date, ac.subject, ac.test_name,
                   ac.score, ac.max_score, ac.memo
            FROM academy_scores ac
            WHERE ac.student_id=?
        """
        params = [student_id]
        if subject_filter:
            query += " AND ac.subject=?"
            params.append(subject_filter)
        query += " ORDER BY ac.date DESC, ac.id DESC"
        cur.execute(query, params)
        rows = cur.fetchall()
        conn.close()

        if not rows:
            st.info("해당 조건의 학원 성적이 없습니다.")
            return

        for sid, dt, subj, test_name, score, max_score, memo in rows:
            with st.expander(f"{dt} • {subj} • {test_name} • {score}/{max_score}"):
                try:
                    d_val = datetime.strptime(dt, "%Y-%m-%d").date()
                except Exception:
                    d_val = date.today()

                with st.form(f"dm_academy_score_form_{sid}"):
                    d_input = st.date_input("날짜", value=d_val, key=f"dm_academy_date_{sid}")
                    subj_input = st.text_input("과목", value=subj, key=f"dm_academy_subj_{sid}")
                    test_input = st.text_input("시험명", value=test_name, key=f"dm_academy_test_{sid}")
                    score_input = st.number_input(
                        "점수",
                        min_value=0.0, max_value=200.0,
                        value=float(score) if score is not None else 0.0,
                        key=f"dm_academy_score_{sid}",
                    )
                    max_input = st.number_input(
                        "만점",
                        min_value=0.0, max_value=200.0,
                        value=float(max_score) if max_score is not None else 100.0,
                        key=f"dm_academy_max_{sid}",
                    )
                    memo_input = st.text_area(
                        "메모",
                        value=memo or "",
                        key=f"dm_academy_memo_{sid}",
                    )

                    c1, c2 = st.columns(2)
                    with c1:
                        save_btn = st.form_submit_button("💾 수정 저장")
                    with c2:
                        del_btn = st.form_submit_button("🗑 삭제")

                    if save_btn:
                        update_academy_score(
                            sid,
                            d_input.strftime("%Y-%m-%d"),
                            subj_input.strip(),
                            test_input.strip(),
                            score_input,
                            max_input,
                            memo_input.strip(),
                        )
                        st.success("수정 완료")
                        st.rerun()
                    if del_btn:
                        delete_academy_score(sid)
                        st.warning("삭제 완료")
                        st.rerun()

    # =============== 학원 진도 관리 ===============
    elif mode == "학원 진도":
        students = get_students()
        if not students:
            st.info("학생이 없습니다.")
            return

        s_opts = {
            f"{name} ({grade}, {school})": sid
            for sid, name, school, grade, phone, memo in students
        }
        s_label = st.selectbox(
            "학생 선택",
            list(s_opts.keys()),
            key="dm_progress_student",
        )
        student_id = s_opts[s_label]

        subject = st.text_input(
            "과목 필터 (비우면 전체)",
            key="dm_progress_subject",
        ).strip()
        subject_filter = subject if subject else None

        conn = get_connection()
        cur = conn.cursor()
        query = """
            SELECT p.id, p.date, s.name, c.name,
                   p.subject, p.unit, p.memo
            FROM academy_progress p
            JOIN students s ON p.student_id=s.id
            LEFT JOIN classes c ON p.class_id=c.id
            WHERE p.student_id=?
        """
        params = [student_id]
        if subject_filter:
            query += " AND p.subject=?"
            params.append(subject_filter)
        query += " ORDER BY p.date DESC, p.id DESC"
        cur.execute(query, params)
        rows = cur.fetchall()
        conn.close()

        if not rows:
            st.info("해당 조건의 진도 기록이 없습니다.")
            return

        for pid, dt, sname, cname, subj, unit, memo in rows:
            title = f"{dt} • {cname or '-'} • {subj} • {unit}"
            with st.expander(title):
                try:
                    d_val = datetime.strptime(dt, "%Y-%m-%d").date()
                except Exception:
                    d_val = date.today()

                with st.form(f"dm_progress_form_{pid}"):
                    d_input = st.date_input("날짜", value=d_val, key=f"dm_prog_date_{pid}")
                    subj_input = st.text_input("과목", value=subj, key=f"dm_prog_subj_{pid}")
                    unit_input = st.text_input("단원/교재/페이지", value=unit or "", key=f"dm_prog_unit_{pid}")
                    memo_input = st.text_area("메모", value=memo or "", key=f"dm_prog_memo_{pid}")

                    c1, c2 = st.columns(2)
                    with c1:
                        save_btn = st.form_submit_button("💾 수정 저장")
                    with c2:
                        del_btn = st.form_submit_button("🗑 삭제")

                    if save_btn:
                        update_academy_progress_record(
                            pid,
                            d_input.strftime("%Y-%m-%d"),
                            subj_input.strip(),
                            unit_input.strip(),
                            memo_input.strip(),
                        )
                        st.success("수정 완료")
                        st.rerun()
                    if del_btn:
                        delete_academy_progress_record(pid)
                        st.warning("삭제 완료")
                        st.rerun()

    # =============== 출석 관리 ===============
    else:  # mode == "출석"
        classes = get_classes()
        date_value = st.date_input("조회 날짜", value=date.today(), key="dm_att_date")
        date_str = date_value.strftime("%Y-%m-%d")

        class_id_filter = None
        if classes:
            class_opts = ["(전체)"] + [
                f"{name} ({level})" for cid, name, level, memo in classes
            ]
            class_map = {
                f"{name} ({level})": cid
                for cid, name, level, memo in classes
            }
            class_label = st.selectbox("반 필터", class_opts, key="dm_att_class")
            if class_label != "(전체)":
                class_id_filter = class_map[class_label]

        records = get_attendance_records(date_str, class_id_filter)
        if not records:
            st.info("해당 날짜에 출결 기록이 없습니다.")
            return

        st.caption("각 기록을 펼쳐서 출결/과제/테스트 상태를 수정하거나 삭제할 수 있습니다.")

        for (aid, dt, time_str, status, hw, test, via,
             s_name, school, grade, class_name) in records:
            title = f"{time_str} • {s_name} • {class_name or '-'} • {status}"
            with st.expander(title):
                with st.form(f"dm_att_form_{aid}"):
                    st.markdown(f"- 날짜: **{dt}**")
                    st.markdown(f"- 학생: **{s_name} ({school}, {grade})**")
                    st.markdown(f"- 반: **{class_name or '-'}**")
                    st.markdown(f"- 입력 경로: **{via}**")

                    status_input = st.selectbox(
                        "출결 상태",
                        ["정상출석", "지각", "미인정결석"],
                        index=["정상출석", "지각", "미인정결석"].index(status),
                        key=f"dm_att_status_{aid}",
                    )
                    hw_input = st.selectbox(
                        "과제",
                        ["○", "△", "X"],
                        index=["○", "△", "X"].index(hw or "○"),
                        key=f"dm_att_hw_{aid}",
                    )
                    test_input = st.selectbox(
                        "일일 테스트",
                        ["○", "△", "X"],
                        index=["○", "△", "X"].index(test or "○"),
                        key=f"dm_att_test_{aid}",
                    )

                    c1, c2 = st.columns(2)
                    with c1:
                        save_btn = st.form_submit_button("💾 수정 저장")
                    with c2:
                        del_btn = st.form_submit_button("🗑 삭제")

                    if save_btn:
                        update_attendance_record(
                            aid,
                            status_input,
                            hw_input,
                            test_input,
                        )
                        st.success("수정 완료")
                        st.rerun()
                    if del_btn:
                        delete_attendance_record(aid)
                        st.warning("삭제 완료")
                        st.rerun()


    # 관리자 승인 대기
    st.markdown("#### 관리자 승인 대기 목록")
    waiting = get_waiting_admins()
    if not waiting:
        st.info("승인 대기 중인 관리자가 없습니다.")
    else:
        for uid, username in waiting:
            cols = st.columns([3, 1, 1])
            cols[0].markdown(f"- `{username}` (ID: {uid})")
            if cols[1].button("승인", key=f"approve_{uid}"):
                approve_admin(uid, True)
                st.success(f"{username} 승인 완료")
                st.rerun()
            if cols[2].button("거절", key=f"reject_{uid}"):
                approve_admin(uid, False)
                st.warning(f"{username} 거절 처리")
                st.rerun()

    st.markdown("---")
    st.markdown("#### 👥 전체 계정 활성/정지 관리")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, username, role, is_approved, is_active
        FROM users
        WHERE role != 'master'
        ORDER BY role, username
        """
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        st.info("관리 대상 계정이 없습니다.")
    else:
        for uid, username, role, is_approved, is_active in rows:
            c1, c2, c3 = st.columns([3, 1, 1])
            status_text = "활성" if is_active else "정지"
            c1.write(f"`{username}` ({role}) - 상태: **{status_text}**")
            if c2.button("활성화", key=f"user_on_{uid}"):
                set_user_active(uid, True)
                st.success(f"{username} 계정을 활성화했습니다.")
                st.rerun()
            if c3.button("정지", key=f"user_off_{uid}"):
                set_user_active(uid, False)
                st.warning(f"{username} 계정을 정지했습니다.")
                st.rerun()


# ============== 학생 화면 ==============

def student_dashboard():
    st.markdown("### 👋 대시보드")
    user = st.session_state["user"]
    student_id = user["student_id"]

    school_rows = get_scores_for_student("school_scores", student_id)
    academy_rows = get_scores_for_student("academy_scores", student_id)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 🏫 최근 학교 성적")
        if not school_rows:
            st.info("학교 성적 기록이 아직 없습니다.")
        else:
            last = school_rows[-3:]
            data = [
                {
                    "날짜": r[0],
                    "과목": r[1],
                    "시험명": r[2],
                    "점수": r[3],
                    "만점": r[4],
                }
                for r in last
            ]
            st.table(pd.DataFrame(data))

    with col2:
        st.markdown("#### 📊 최근 학원 성적")
        if not academy_rows:
            st.info("학원 성적 기록이 아직 없습니다.")
        else:
            last = academy_rows[-3:]
            data = [
                {
                    "날짜": r[0],
                    "과목": r[1],
                    "시험명": r[2],
                    "점수": r[3],
                    "만점": r[4],
                }
                for r in last
            ]
            st.table(pd.DataFrame(data))


def student_notice_view():
    st.markdown("### 📢 공지사항")
    notices = get_notices()
    if not notices:
        st.info("등록된 공지가 없습니다.")
    else:
        for nid, title, content, pinned, created_at in notices:
            header = f"📌 {title}" if pinned else title
            with st.expander(header, expanded=pinned):
                st.markdown(f"*작성 시각: {created_at}*")
                st.write(content)


def student_progress_view():
    st.markdown("### 📚 나의 학원 진도")
    user = st.session_state["user"]
    student_id = user["student_id"]

    subject = st.text_input("과목 필터 (비우면 전체)").strip()
    subject_filter = subject if subject else None

    conn = get_connection()
    cur = conn.cursor()
    query = """
        SELECT p.date, p.subject, p.unit, p.memo, c.name
        FROM academy_progress p
        LEFT JOIN classes c ON p.class_id=c.id
        WHERE p.student_id=?
    """
    params = [student_id]
    if subject_filter:
        query += " AND p.subject=?"
        params.append(subject_filter)
    query += " ORDER BY p.date DESC"
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    if not rows:
        st.info("진도 기록이 없습니다.")
    else:
        data = []
        for dt, subj, unit, memo, c_name in rows:
            data.append(
                {
                    "날짜": dt,
                    "반": c_name,
                    "과목": subj,
                    "단원/교재": unit,
                    "메모": memo,
                }
            )
        st.dataframe(pd.DataFrame(data), use_container_width=True)


def student_score_view_common(table_name, title):
    st.markdown(f"### {title}")
    user = st.session_state["user"]
    student_id = user["student_id"]

    subject = st.text_input("과목 필터 (비우면 전체)").strip()
    subject_filter = subject if subject else None

    rows = get_scores_for_student(table_name, student_id, subject_filter)
    if not rows:
        st.info("성적 기록이 없습니다.")
        return

    data = []
    for dt, subj, exam_nm, score, max_score in rows:
        data.append(
            {
                "날짜": dt,
                "과목": subj,
                "시험명": exam_nm,
                "점수": score,
                "만점": max_score,
            }
        )
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True)

    df_plot = df.copy()
    df_plot["날짜"] = pd.to_datetime(df_plot["날짜"])
    df_plot.set_index("날짜", inplace=True)
    st.line_chart(df_plot["점수"])

    with st.expander("📄 인쇄용 성적표 보기"):
        st.image("logo.png", width=120)
        st.markdown("#### 성적 리포트")
        st.write(f"학생 계정: `{st.session_state['user']['username']}`")
        st.table(df)
        st.caption(
            "※ 브라우저 인쇄(Ctrl+P / Command+P)로 출력 또는 "
            "PDF 저장이 가능합니다."
        )


def student_timetable_view():
    st.markdown("### 🗓 내 시간표")
    user = st.session_state["user"]
    student_id = user["student_id"]

    classes = get_classes_for_student(student_id)
    if not classes:
        st.info("배정된 반이 없습니다. 관리자에게 문의하세요.")
        return

    class_ids = [cid for cid, name, level in classes]
    rows = get_timetables_for_classes(class_ids)

    if not rows:
        st.info("시간표가 없습니다.")
        return

    weekdays = ["월", "화", "수", "목", "금", "토", "일"]

    data = []
    for (tid, cname, weekday, st_time_str, en_time_str,
         subj, room, teacher, memo, class_id) in rows:
        data.append(
            {
                "반ID": class_id,
                "반": cname,
                "요일": weekdays[weekday],
                "시작": st_time_str,
                "종료": en_time_str,
                "과목": subj,
                "강의실": room,
                "선생님": teacher,
                "메모": memo,
            }
        )
    df = pd.DataFrame(data)

    class_name_map = {cid: name for cid, name, level in classes}
    class_label = st.selectbox(
        "하이라이트할 반 선택",
        [class_name_map[cid] for cid in class_ids],
    )
    highlighted_id = None
    for cid, name in class_name_map.items():
        if name == class_label:
            highlighted_id = cid
            break

    def highlight_row(row):
        if "반ID" not in row.index:
            return [""] * len(row)
        if row["반ID"] == highlighted_id:
            return ["background-color: #2b6cb0; color: white"] * len(row)
        return [""] * len(row)

    # 스타일 적용은 반ID 포함 df로, 표시는 숨김
    df_show = df.copy()
    sty = df_show.style.apply(highlight_row, axis=1)
    try:
        sty = sty.hide(axis="columns", subset=["반ID"])
    except Exception:
        try:
            sty = sty.hide_columns(["반ID"])
        except Exception:
            pass

    st.dataframe(sty, use_container_width=True)


def student_vocab_view():
    st.markdown("### 📘 내 단어장")
    user = st.session_state["user"]
    student_id = user["student_id"]

    sets = get_assigned_vocab_sets_for_student(student_id)
    if not sets:
        st.info("배정된 단어장이 없습니다.")
        return

    set_opts = {f"{name} ({level})": sid for sid, name, desc, level in sets}
    set_label = st.selectbox("단어장 선택", list(set_opts.keys()))
    set_id = set_opts[set_label]

    items = get_vocab_items(set_id)
    if not items:
        st.info("이 단어장에 아직 단어가 없습니다.")
        return

    tab1, tab2, tab3 = st.tabs(["학습 모드", "암기 모드", "퀴즈 모드 (4지선다)"])

    # 학습 모드
    with tab1:
        data = []
        for vid, w, m, pos, ex_en, ex_ko, tags, diff in items:
            data.append(
                {
                    "단어": w,
                    "뜻": m,
                    "품사": pos,
                    "예문(영)": ex_en,
                    "예문(한)": ex_ko,
                    "태그": tags,
                    "난이도": diff,
                }
            )
        st.dataframe(pd.DataFrame(data), use_container_width=True)

    # 암기 모드
    with tab2:
        st.caption("단어를 보고 뜻과 예문을 펼쳐서 암기용으로 사용하세요.")
        for vid, w, m, pos, ex_en, ex_ko, tags, diff in items:
            title = f"{w} ({pos})" if pos else w
            with st.expander(title):
                st.markdown(f"**뜻:** {m}")
                if ex_en:
                    st.markdown(f"**예문(영):** {ex_en}")
                if ex_ko:
                    st.markdown(f"**예문(한):** {ex_ko}")
                if tags:
                    st.caption(f"태그: {tags}")

    # 퀴즈 모드 (4지선다)
    with tab3:
        st.caption("영단어를 보고 알맞은 한국어 뜻을 고르세요. (4지선다)")

        key_quiz = f"vocab_quiz_{set_id}"
        if key_quiz not in st.session_state:
            st.session_state[key_quiz] = {
                "questions": None,
                "started": False,
            }

        quiz_state = st.session_state[key_quiz]

        if not quiz_state["started"]:
            num_total = len(items)
            default_n = min(10, num_total)
            n_questions = st.number_input(
                "문항 수",
                min_value=1,
                max_value=num_total,
                value=default_n,
                step=1,
            )
            if st.button("퀴즈 시작"):
                selected_items = random.sample(items, int(n_questions))
                all_meanings = [m for _, _, m, *_ in items]

                questions = []
                for vid, w, m, pos, ex_en, ex_ko, tags, diff in selected_items:
                    correct = m
                    wrong_pool = [mm for mm in all_meanings if mm != correct]
                    if len(wrong_pool) >= 3:
                        wrongs = random.sample(wrong_pool, 3)
                    else:
                        wrongs = wrong_pool[:3]
                    options = wrongs + [correct]
                    random.shuffle(options)
                    correct_idx = options.index(correct)
                    questions.append(
                        {
                            "vocab_item_id": vid,
                            "word": w,
                            "options": options,
                            "correct_idx": correct_idx,
                        }
                    )

                quiz_state["questions"] = questions
                quiz_state["started"] = True
                st.session_state[key_quiz] = quiz_state
                st.rerun()
        else:
            questions = quiz_state["questions"]
            answers = []

            for i, q in enumerate(questions):
                st.markdown(f"**Q{i+1}. {q['word']}**")
                ans = st.radio(
                    "뜻 선택",
                    q["options"],
                    key=f"vocab_q_{set_id}_{i}",
                )
                answers.append(ans)
                st.write("")

            if st.button("채점하기"):
                correct_count = 0
                for i, q in enumerate(questions):
                    if answers[i] == q["options"][q["correct_idx"]]:
                        correct_count += 1
                total = len(questions)
                percent = (correct_count / total * 100.0) if total > 0 else 0.0

                st.success(
                    f"정답 {correct_count}/{total}개, "
                    f"정답률 {percent:.1f}%"
                )

                save_vocab_quiz_result(set_id, student_id,
                                       correct_count, total)

                st.session_state[key_quiz] = {
                    "questions": None,
                    "started": False,
                }

        st.caption(
            "※ 단어장 퀴즈 기록은 관리자 화면 "
            "('단어장 관리 → 결과 요약')에서 확인 가능합니다."
        )


def student_exam_documents_view():
    st.markdown("### 📄 내 시험지 / 자료")
    user = st.session_state["user"]
    student_id = user["student_id"]

    docs = get_exam_documents_for_student(student_id)
    if not docs:
        st.info("등록된 시험지 / 자료가 없습니다.")
        return

    subjects = sorted({d[1] for d in docs if d[1]})
    subj_filter = st.selectbox(
        "과목 필터 (선택)",
        ["(전체)"] + subjects,
    )

    filtered = []
    for row in docs:
        if subj_filter == "(전체)" or row[1] == subj_filter:
            filtered.append(row)

    for (doc_id, subj, etype, ename, edate, tags,
         memo, fpath, oname, uploaded_at) in filtered:
        title = f"{edate} • {subj} • {ename}"
        with st.expander(title):
            st.write(f"유형: {etype}")
            st.write(f"태그: {tags}")
            st.write(f"메모: {memo}")
            st.write(f"업로드 시간: {uploaded_at}")
            try:
                with open(fpath, "rb") as f:
                    file_bytes = f.read()
                if fpath.lower().endswith((".png", ".jpg", ".jpeg")):
                    st.image(
                        file_bytes,
                        caption=oname,
                        use_container_width=True,
                    )
                else:
                    st.download_button(
                        label="📎 파일 다운로드",
                        data=file_bytes,
                        file_name=oname,
                        mime="application/pdf",
                    )
            except FileNotFoundError:
                st.error(f"파일을 찾을 수 없습니다. (경로: {fpath})")


# ============== 메인 ==============

def main():
    st.set_page_config(page_title="학원 관리 시스템", layout="wide")
    init_db()
    promote_all_students_if_needed()

    # ===== 상단 여백 제거 CSS =====
    st.markdown("""
        <style>
            .main > div:first-child {
                padding-top: 0 !important;
            }
            .block-container {
                padding-top: 0.5rem !important;
                padding-bottom: 0.5rem !important;
            }
        </style>
    """, unsafe_allow_html=True)


    # 세션 상태 초기화
    if "theme" not in st.session_state:
        st.session_state["theme"] = "light"
    if "user" not in st.session_state:
        st.session_state["user"] = None

    # 로그인 안 되어 있으면 로그인 화면만
    if not st.session_state["user"]:
        apply_theme()
        login_page()
        return

    # 로그인 후
    apply_theme()
    menu_value = render_sidebar()
    user = st.session_state["user"]

    # 관리자 승인 대기
    if user["role"] == "admin" and not user["is_approved"]:
        st.markdown("### 관리자 승인 대기 중")
        st.info("마스터가 승인을 완료하면 관리자 기능을 사용할 수 있습니다.")
        return

    # 학생 화면
    if user["role"] == "student":
        menu = menu_value or "대시보드"

        if menu == "대시보드":
            student_dashboard()
        elif menu == "공지사항":
            student_notice_view()
        elif menu == "내 학원 진도":
            student_progress_view()
        elif menu == "내 학원 성적":
            student_score_view_common("academy_scores", "📊 나의 학원 성적")
        elif menu == "내 학교 성적":
            student_score_view_common("school_scores", "🏫 나의 학교 성적")
        elif menu == "내 시간표":
            student_timetable_view()
        elif menu == "내 단어장":
            student_vocab_view()
        elif menu == "내 시험지 자료":
            student_exam_documents_view()

    # 관리자 / 마스터 화면
    else:
        is_master = (user["role"] == "master")
        menu = menu_value or "대시보드"

        if menu == "대시보드":
            admin_dashboard()
        elif menu == "공지 관리":
            admin_notice_management()
        elif menu == "학생 관리":
            admin_student_management()
        elif menu == "수업 관리":
            admin_lesson_management()          # ← 여기에서 진도/출석까지 통합
        elif menu == "단어장 관리":
            admin_vocab_management()
        elif menu == "성적 관리":
            # 성적 관리 화면 내부에서 탭으로 학원/학교 나눔
            admin_score_management()
        elif menu == "시간표 관리":
            admin_timetable()
        elif menu == "반(클래스) 관리":
            admin_class_management()
        elif menu == "관리자 승인" and is_master:
            master_admin_approval()

if __name__ == "__main__":
    main()
