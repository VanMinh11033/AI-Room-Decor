# API Documentation

FastAPI exposes interactive Swagger documentation at:

```text
http://localhost:8000/docs
```

Main groups:

- `/api/auth/*`
- `/api/users/*`
- `/api/products/*`
- `/api/categories`
- `/api/admin/*`

All admin endpoints require a valid JWT access token for a user with `ADMIN` role.

