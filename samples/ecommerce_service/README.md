# E-Commerce Microservice (RepoMind Bundled Sample Repository)

A realistic, self-contained Python microservice designed for demonstrating RepoMind's architectural analysis, static code intelligence, hybrid search, dependency graph, and change-impact analysis.

## Architecture & Module Overview
- `models.py`: Domain data models (`User`, `Product`, `Order`, `PaymentTransaction`, `Address`).
- `database.py`: In-memory repository pattern, mock database connections, and session management.
- `auth.py`: User authentication, password hashing, JWT token verification, and role-based permissions.
- `orders.py`: Order placement, price calculation, inventory reservation, and checkout orchestration.
- `payments.py`: Payment gateway integration (`PaymentGateway`, `StripeAdapter`, `PayPalAdapter`).
- `notifications.py`: Customer communication via Email and SMS with template formatting.
- `utils.py`: Security hashing, currency conversion, tax calculation, and string validation.
- `orphan_task.py`: Isolated background cleanup worker (intentionally not imported by other modules to demonstrate RepoMind's orphan detection).
