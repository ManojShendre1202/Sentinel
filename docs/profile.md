# Manoj Shendre — Candidate Profile

> Single source of truth read by both consumers: Claude's scoring step (full file, needs project depth/impact for judgment quality) and Gemini's form-filling step (Personal Details / Education / Experience / Skills — literal answerable fields).

---

## Personal Details
- **Name:** Manoj Shendre (documents: Manoj V)
- **Email:** manojshendre.1202@gmail.com
- **Phone:** +91 8884812422
- **Location:** Bangalore, India (open to relocation)
- **LinkedIn:** https://www.linkedin.com/in/manoj-shendre-a40b932b0/
- **GitHub:** https://github.com/ManojShendre1202
- **Portfolio:** https://manojshendre.com (live Readar demo: https://manojshendre.com/readar/)

---

## Education
- **Degree:** B.Tech — Aeronautical Engineering
- **College:** Bharath University, Chennai
- **Year:** 2023

## Internship
- **Company:** Hindustan Aeronautics Limited (HAL)
- **Duration:** 1 month (2022/2023)
- **Work:** Documented end-to-end manufacturing process of Chetak helicopters

## Publications & Research
1. **Investigation of Static Aeroelastic Analysis and Flutter Characterization of a Slender Straight Wing** — International Journal of Automotive and Mechanical Engineering (IJAME), 2024. DOI: [10.15282/ijame.21.2.2024.3.0866](https://doi.org/10.15282/ijame.21.2.2024.3.0866)
2. **Static Aeroelastic Characterization of a Slender Straight Wing** — International Journal of Vehicle Structures & Systems (IJVSS). DOI: [10.4273/ijvss.16.1.04](https://doi.org/10.4273/ijvss.16.1.04)
3. **Individual Color Vision Prediction from Cone Ratios: A Computational Approach** — independent research deriving a computational model predicting individual color perception from cone ratios in the human visual system. DOI: [10.21203/rs.3.rs-7726344/v1](https://doi.org/10.21203/rs.3.rs-7726344/v1)

---

## Experience

### Kynea Solutions LLP — Machine Learning Engineer
**Period:** May 2024 – Present, Bangalore, India

7 of 10 client projects — core development or lead. Built and owns the **Dockyard Workflow Engine** — a domain-agnostic drawing-processing engine built from scratch (custom Python worker pool, multi-stage pipelines with human-review gates, real-time WebSocket log streaming, TCP signal-based dispatch, crash recovery).

**Featured projects (7):**

1. **Railways — Automated BOM Generation** (Production, 95% reduction — 1 month → 2 hours). Reads PDFs and images of railway engineering drawings — some with image sizes near a lakh pixels. Encodes complex domain flowchart logic in Python to identify components, interpret symbols, and generate complete Bills of Materials automatically. Handles scale variations, noisy scans, and domain-specific notation. Before: 10-20 engineers, ~1 month per drawing set. After: 2-3 people, ~2 hours including human verification. Stack: Python, OpenCV, OCR, Azure.

2. **Shipbuilding — Cable Systems — Cable Routing System** (UAT, lakhs of cables / lakhs of km routed, sole developer). Parses complex DXF ship drawings to identify multiple decks and cable trays — a significant challenge given the varied curves, angles, and representations across different ship departments. Builds a universal topological graph of the ship, then routes cables using a custom Flood Fill + Dijkstra hybrid algorithm that accounts for tray capacity, routing constraints, and cable specifications. Stack: Python, ezdxf, Shapely, Dijkstra, graph algorithms.

3. **Shipbuilding — Hull Engineering — Hull Weld Seam BOM** (In Dev, thousands of weld spots per drawing, sole developer + project lead). Second project within the shipbuilding domain — a different department, demonstrating repeat client engagement. Detects thousands of welding spots and blocks across hull drawings, then computes weld seam lengths via on-spot geometric calculation. Deliberately contrasts with the cable routing approach — no graph-based algorithm, no ML models; pure shape analysis because the problem structure demands it. Stack: Python, ezdxf, Shapely, OpenCV.

4. **Automotive — Automotive Wiring Harness BOM** (Near-Prod, ~95% reduction — 2-3 days → 1 hour). Processes complex automotive wiring harness drawings — among the most intricate engineering drawings in any domain. Element detection using a locally-trained FasterRCNN model identifies connectors, terminals, splices, and wiring components. Custom graph/association logic (core contribution) links detected elements to tables and BOM entries, calculates wiring lengths and bundle configurations, and generates complete manufacturing BOMs. Before: 3-4 engineers, ~2-3 days per harness drawing set. After: ~1 hour including manual verification. Stack: FasterRCNN, AWS, Azure, OpenCV, OCR.

5. **Defense Shipbuilding — Cable Routing POC** (Delivered, sent alone, on-site, no internet, 120m+ ships, sole developer). Sent alone by the company to deliver a live proof-of-concept on-site at a defense shipyard, with no internet access. Ships 120+ meters in length with DXF and SVG format drawings. Adapted the cable routing engine on-site for the new format, ran live demonstrations, and delivered a technically successful POC. Stack: Python, ezdxf, Shapely, OpenCV.

6. **Aerospace — Aircraft BOM Generation** (In Dev, Airbus + Boeing aircraft database, sole developer). Processes complex scanned engineering drawings for Airbus and Boeing aircraft databases. Defining technical choice: table detection without ML models — a deliberate engineering constraint, since fax-format unstructured tables in scanned aerospace drawings have enough consistent geometric structure that a pure OpenCV approach is more robust and maintainable than a neural network. Advanced OpenCV for noisy scan handling and optimized cross-document reference resolution across large drawing datasets. Stack: Python, OpenCV, OCR.

7. **Hubbell — SAP Deduction Validation** (Production, 1+ year live, primary owner). ML model that validates the genuineness of deductions across SAP enterprise documents. The only non-drawing project — demonstrates stack versatility beyond computer vision, enterprise data pipeline experience, and SAP domain knowledge. Primary ownership for 1+ year: model retraining when distribution shifts, dashboard management, handling all client change requests, and production monitoring. Stack: Python, Azure ADF, ADLS, SQL.

---

## Personal Projects

**Readar — Graph RAG Chat Engine.** A retrieval-augmented chatbot built from scratch — no vector DB, no LangChain. Paragraphs become nodes in a similarity graph, cosine-similarity edges connect related ideas, BFS hop-traversal retrieves a candidate subgraph per question, and a cross-encoder reranks candidates before anything reaches Gemini (cuts tokens sent to the model by ~75-85%). Multi-turn memory is retrieval-augmented rather than history replay — each turn's hidden summary is embedded into its own small per-session graph, keeping cost flat as conversations grow instead of scaling with turn count. Live demo ingests real documentation end-to-end (DOM-parsed, 1,049 nodes / 549,676 similarity edges in the demo graph), with WebSocket token streaming and clickable citations that scroll to and highlight the source paragraph. Self-hosted end-to-end on an Oracle Cloud (OCI) ARM VM — Dockerized Django + WebSocket services behind Nginx, load-tested under real concurrent chat sessions. Stack: Python, Django, WebSockets, Gemini API, nomic-embed-text-v1.5, cross-encoder reranking, Docker, Nginx, OCI. Live at manojshendre.com/readar.

---

## Skills

| Category | Skills |
|----------|--------|
| AI, ML & LLM Engineering | Machine Learning, Deep Learning, Generative AI, Large Language Models (LLMs), Retrieval-Augmented Generation (RAG), Google Gemini API, Prompt Engineering, Vector Embeddings, Semantic Search, Natural Language Processing (NLP) |
| Computer Vision & ML | OpenCV (advanced), FasterRCNN, OCR, Azure Computer Vision, ChangeFormer, PyTorch |
| Drawing & Geometry | ezdxf, Shapely, DXF / SVG / PDF processing |
| Algorithms | Dijkstra, Flood Fill, Graph Algorithms, Geometric Computation, BFS / DFS |
| Cloud & Infrastructure | Azure ADF, Azure ADLS, AWS, Oracle Cloud Infrastructure (OCI), Docker, Nginx |
| Backend & Systems | Python, Django, FastAPI, WebSockets, Custom Worker Pools, SQL |
| Databases | MSSQL, MySQL, ArangoDB, Azure Data Lake, Firebase, PostgreSQL, MongoDB, SAP |

---

## Preferences

- **Target roles:** Computer Vision Engineer (most accurate fit), AI/ML Engineer, Backend Engineer (Python), Data Engineer (Azure ADF/ADLS angle), Software Engineer — AI/ML, Research Engineer
- **Target CTC floor:** 20 LPA (do not go below)
- **Target CTC ask:** 25-28 LPA
- **Current CTC:** 10 LPA
- **Target company tiers:**
  - Tier 1: L&T Mindtree, Bosch, Siemens, Dassault Systèmes, Autodesk, ANSYS
  - Tier 2: Capgemini Engineering, Honeywell, Accenture AI, TCS Research, Wipro AI
  - Tier 3: Sarvam AI, Ideaforge, General Aeronautics, Juspay, Darwinbox
  - Tier 4 (stretch): Airbus India, Boeing India, Microsoft, Google
- **Excluded:** tiny/early-stage startups
- **Location:** Bangalore, India (primary — not open to relocation); remote acceptable
