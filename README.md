# App Review Intelligence

Analytics tool to explore curated App Store and Play Store reviews with trend graphs and natural-language Q&A (RAG).

---

## 📖 Documentation Index

* [Getting Started Guide](docs/GETTING_STARTED.md)**: Setup dependencies, configure Supabase migrations, and launch local dev servers.
* [System Architecture](docs/ARCHITECTURE.md)**: Canonical design specification covering data schemas, vector search, and the RAG pipeline.
* [Development History](docs/DEVELOPMENT_HISTORY.md)**: Log of completed implementation phases, features, and historical design choices.
* [AI Assistant Rules](docs/AI_ASSISTANT_RULES.md)**: Standards for styling, tests, logs, and directory layouts.

---

## 🛠️ Quick Start

1. **Configure Environment:**
   ```bash
   cp .env.example .env
   # Add your Supabase & Gemini credentials in .env
   ```
2. **Apply Migrations:**
   Copy the SQL contents of `supabase/migrations/001_init.sql` and `002_vector_search.sql` into the Supabase SQL editor and execute them.
3. **Install Dependencies:**
   ```bash
   make install
   ```
4. **Run Application:**
   * Run API: `make run-api` (Port 8000)
   * Run Frontend: `make run-web` (Port 3000)
5. **Run Tests:**
   ```bash
   make test
   ```

---

## 👥 Authors & License

* **Author:** Ajeya Siddhartha ([ajeyasiddharth@gmail.com](mailto:ajeyasiddharth@gmail.com))
* **License:** Distributed under the MIT License. See [LICENSE](LICENSE) for more details (free to use, modify, and distribute with attribution).

