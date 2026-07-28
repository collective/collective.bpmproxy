# Plone Operaton App

This project is a Spring Boot application running Operaton BPM (Camunda fork). It includes web apps (Cockpit, Tasklist, Admin, Welcome) with custom plugins.

## Prerequisites

- Java 17
- Maven
- (Optional) Nix for reproducible builds and containerization

## Building the Project

You can build the project using Maven or Nix.

**Using Maven:**
```bash
./mvnw clean install
```

**Using Nix:**
```bash
make build
```
This uses `flake.nix` and `mvn2nix` to build the project.

## Running the Application (Database Configuration)

### With PostgreSQL (Default)
By default, the application is configured to use a PostgreSQL database. Ensure you have a PostgreSQL instance running at `localhost:5432` with a database named `postgres` and credentials `postgres`/`postgres`.
```bash
./mvnw spring-boot:run
```

### With H2 Database (In-Memory)
To run the application without requiring a PostgreSQL instance, you can activate the `h2` profile:
```bash
./mvnw spring-boot:run -Dspring-boot.run.profiles=h2
```
Or by setting the environment variable:
```bash
SPRING_PROFILES_ACTIVE=h2 ./mvnw spring-boot:run
```
*Note: The `h2` profile configures an in-memory database (`jdbc:h2:mem:operaton`), so all data is lost when the application shuts down.*

## Security Configuration

### Plone JWT Authentication
Requests from Plone to the REST API (`/engine-rest/*`) are authenticated by a custom JWT filter present in every profile. 
The application validates the JWT using the public key specified in `application.yml`:
```yaml
plone:
  public-key: ec-ed25519-pub-key.pem
```
Ensure the `ec-ed25519-pub-key.pem` file is correctly placed in the resources or accessible classpath.

### OAuth2 / OIDC Login
An `oauth2` profile is available which integrates Keycloak for OIDC login on the Operaton webapps (Cockpit/Tasklist/Admin/Welcome). 
To activate it:
```bash
SPRING_PROFILES_ACTIVE=oauth2 ./mvnw spring-boot:run
```
*(You can combine profiles by comma-separating them, e.g., `SPRING_PROFILES_ACTIVE=h2,oauth2`)*

In development, a Keycloak instance is typically provided by `devenv` (realm "plone"). The OAuth2 client relies on the following environment variables (with defaults):
- `KEYCLOAK_ISSUER_URI` (default: `http://localhost:8082/realms/plone`)
- `KEYCLOAK_CLIENT_SECRET` (default: `operaton-secret`)
- `OPERATON_POST_LOGOUT_REDIRECT_URI` (default: `http://localhost:8081/`)

## Makefile Commands

- `make build`: Build the project with Nix.
- `make test`: Run Maven tests and generate JaCoCo coverage reports (available in `target/site/jacoco`).
- `make dist`: Build a container image and load it into Podman.
- `make push`: Push the image to a container registry.
- `make fetch-plugins`: Download custom frontend plugins for the Operaton webapps.
