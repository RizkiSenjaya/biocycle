-- Script untuk membuat tabel users dengan role-based access control
-- Jalankan script ini di MySQL untuk membuat tabel users

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    uid VARCHAR(255) UNIQUE NOT NULL COMMENT 'Firebase UID',
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    role ENUM('admin', 'peternak') DEFAULT 'peternak' NOT NULL,
    status ENUM('pending', 'approved', 'rejected') DEFAULT 'pending' NOT NULL COMMENT 'Status approval untuk pendaftaran',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_email (email),
    INDEX idx_role (role),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Insert admin default (ganti email dengan email admin yang sebenarnya)
-- Password harus dibuat melalui Firebase Auth terlebih dahulu
-- INSERT INTO users (uid, email, name, role, status) 
-- VALUES ('admin-uid-from-firebase', 'admin@biocycle.com', 'Admin BioCycle', 'admin', 'approved');

