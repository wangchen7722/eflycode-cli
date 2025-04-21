CREATE TABLE chat_request (
    id           BIGINT          NOT NULL PRIMARY KEY,
    user_id      BIGINT          NOT NULL,
    model_id     VARCHAR(50)     NOT NULL,
    prompt       TEXT            NULL,              -- ≤32 KB 直接存；>32 KB 建 object_key 放 params
    params       JSON            NOT NULL DEFAULT (JSON_OBJECT()),
    status       ENUM('PENDING','RUNNING','CANCELED','DONE','ERROR')
                                NOT NULL DEFAULT 'PENDING',
    created_at   DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at   DATETIME        NULL,
    finished_at  DATETIME        NULL,
    extra        JSON            NULL,
    INDEX idx_user_time (user_id, created_at DESC),
    INDEX idx_status (status, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;