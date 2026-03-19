# Proyecto: Agora — Empresa: Nexora

Clase de Ingeniería de Software en el Instituto Tecnológico de Mexicali (ITM). El equipo simula una empresa de software con departamentos: Análisis, Diseño, Programación, Testing, QA, Marketing, Administración, Líder y Documentador.

**Rol:** Líder del equipo de Programación (7 personas: 4 frontend, 3 backend). Participación en frontend y backend.

---

## Aplicación

App móvil para el ITM con módulos:

- Mapa del campus (vista 360°)
- Gestor de clubes
- Buzón de quejas
- Autenticación

---

## Stack

- Frontend: React Native + Expo 54
- Backend: FastAPI + SQLAlchemy + python-jose (JWT)
- Base de datos: PostgreSQL
- Testing endpoints: Bruno

---

## Arquitectura

Cliente-servidor por capas:

- Cliente (app móvil)
- Backend:
  - Presentación (FastAPI endpoints)
  - Lógica (servicios)
  - Datos (SQLAlchemy + PostgreSQL)

**Flujo:**

```
Usuario → App → API → Lógica → DB → JSON → App
```

---

## Convenciones técnicas

- HTTP + JSON
- JWT
- Separación frontend/backend
- Backend único acceso a DB
- Organización modular

---

## Repositorio: agora-frontend

### Testing

- Uso de Jest con `jest-expo`
- Uso de `@testing-library/react-native`
- Estructura de pruebas en carpeta dedicada (`__tests__`)
- Coverage habilitado para medir cobertura de código

---

### Calidad de código

- ESLint configurado con `eslint-config-expo`
- Prettier integrado para formateo consistente
- Integración ESLint + Prettier para evitar conflictos

---

### Automatización con Git Hooks

- Uso de Husky para ejecutar validaciones automáticas
- Validación en commits mediante `lint-staged`
- Ejecución de tests antes de push

---

### Control de commits

- Uso de `commitlint` con estándar conventional commits
- Estructura obligatoria de mensajes de commit

---

### Integración continua (CI)

- Configuración de GitHub Actions
- Ejecución automática de tests en cada push

---

### Protección de rama

- Rama `main` protegida
- Requiere Pull Request para integración
- Requiere que los tests pasen antes de merge
- Restricción de bypass de reglas

---

### Flujo de trabajo

- No se permite push directo a `main`
- Uso de ramas de tipo `feature/*`
- Integración mediante Pull Requests
