-- QuizMaster Database Schema

CREATE TABLE IF NOT EXISTS users (
    userid SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    passwordhash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL,
    class VARCHAR(100),
    approved BOOLEAN DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS teacher_classes (
    id SERIAL PRIMARY KEY,
    teacherid INT NOT NULL REFERENCES users(userid) ON DELETE CASCADE,
    class VARCHAR(100) NOT NULL,
    subject VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS enrollments (
    enrollmentid SERIAL PRIMARY KEY,
    studentid INT NOT NULL REFERENCES users(userid) ON DELETE CASCADE,
    class VARCHAR(100) NOT NULL,
    approved BOOLEAN DEFAULT NULL,
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS quizzes (
    quizid SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    difficulty VARCHAR(50) DEFAULT 'Medium',
    availablefrom TIMESTAMP,
    availableto TIMESTAMP,
    attemptlimit INT DEFAULT 1,
    createdby INT REFERENCES users(userid) ON DELETE CASCADE,
    class VARCHAR(100),
    isdraft BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS questions (
    questionid SERIAL PRIMARY KEY,
    quizid INT NOT NULL REFERENCES quizzes(quizid) ON DELETE CASCADE,
    questiontext TEXT NOT NULL,
    optiona VARCHAR(255) NOT NULL,
    optionb VARCHAR(255) NOT NULL,
    optionc VARCHAR(255) NOT NULL,
    optiond VARCHAR(255) NOT NULL,
    correctoption VARCHAR(255) NOT NULL,
    difficulty VARCHAR(50) DEFAULT 'Medium'
);

CREATE TABLE IF NOT EXISTS attempts (
    attemptid SERIAL PRIMARY KEY,
    quizid INT NOT NULL REFERENCES quizzes(quizid) ON DELETE CASCADE,
    studentid INT NOT NULL REFERENCES users(userid) ON DELETE CASCADE,
    attemptno INT DEFAULT 1,
    score FLOAT,
    starttime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    endtime TIMESTAMP
);

CREATE TABLE IF NOT EXISTS responses (
    responseid SERIAL PRIMARY KEY,
    attemptid INT NOT NULL REFERENCES attempts(attemptid) ON DELETE CASCADE,
    questionid INT NOT NULL REFERENCES questions(questionid) ON DELETE CASCADE,
    selectedoption VARCHAR(255),
    iscorrect BOOLEAN,
    submittedat TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS leaderboard (
    leaderboardid SERIAL PRIMARY KEY,
    quizid INT REFERENCES quizzes(quizid) ON DELETE CASCADE,
    studentid INT NOT NULL REFERENCES users(userid) ON DELETE CASCADE,
    totalscore FLOAT DEFAULT 0,
    rank INT,
    class VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS feedback (
    feedbackid SERIAL PRIMARY KEY,
    attemptid INT NOT NULL REFERENCES attempts(attemptid) ON DELETE CASCADE,
    teacherid INT NOT NULL REFERENCES users(userid) ON DELETE CASCADE,
    studentid INT NOT NULL REFERENCES users(userid) ON DELETE CASCADE,
    feedback TEXT,
    comments TEXT,
    createdat TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
