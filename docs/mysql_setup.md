# MySQL Production Setup (JPY101-102)

## Dedykowany użytkownik aplikacji

```sql
CREATE USER 'sunny_user'@'localhost' IDENTIFIED BY 'sunny_pass123';
GRANT SELECT, INSERT, UPDATE, DELETE ON calendar_db.* TO 'sunny_user'@'localhost';
GRANT PROCESS, LOCK TABLES, RELOAD ON *.* TO 'sunny_user'@'localhost';
FLUSH PRIVILEGES;
```

## Backup (cron, codziennie o 2:00)

```bash
0 2 * * * /usr/local/mysql/bin/mysqldump -u sunny_user -psunny_pass123 --single-transaction calendar_db > ~/mysql_backups/calendar_db_$(date +%Y%m%d).sql
```

Backupy zapisywane do `~/mysql_backups/`.
