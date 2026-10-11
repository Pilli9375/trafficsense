"""
TrafficSense — Individual Contribution Report Generator
Generates 4 styled PDFs for each team member using reportlab.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import PageBreak
import os

OUT_DIR = r"C:\Pilli\trafficsense\reports"
os.makedirs(OUT_DIR, exist_ok=True)

# ── Colour palette ──────────────────────────────────────────
NAVY    = colors.HexColor("#0D1B2A")
BLUE    = colors.HexColor("#1565C0")
ACCENT  = colors.HexColor("#00B4D8")
LIGHT   = colors.HexColor("#E8F4FD")
WHITE   = colors.white
GREY    = colors.HexColor("#546E7A")
GREEN   = colors.HexColor("#2E7D32")
BORDER  = colors.HexColor("#BBDEFB")

W, H = A4

# ── Shared styles ───────────────────────────────────────────
def make_styles():
    base = getSampleStyleSheet()

    title = ParagraphStyle("DocTitle",
        parent=base["Normal"], fontSize=22, textColor=WHITE,
        fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=4)

    subtitle = ParagraphStyle("DocSubtitle",
        parent=base["Normal"], fontSize=12, textColor=ACCENT,
        fontName="Helvetica", alignment=TA_CENTER, spaceAfter=2)

    meta = ParagraphStyle("Meta",
        parent=base["Normal"], fontSize=10, textColor=LIGHT,
        fontName="Helvetica", alignment=TA_CENTER, spaceAfter=2)

    section = ParagraphStyle("Section",
        parent=base["Normal"], fontSize=13, textColor=BLUE,
        fontName="Helvetica-Bold", spaceBefore=14, spaceAfter=6,
        borderPad=4)

    body = ParagraphStyle("Body",
        parent=base["Normal"], fontSize=10, textColor=colors.HexColor("#212121"),
        fontName="Helvetica", leading=16, alignment=TA_JUSTIFY, spaceAfter=6)

    bullet = ParagraphStyle("Bullet",
        parent=base["Normal"], fontSize=10, textColor=colors.HexColor("#212121"),
        fontName="Helvetica", leading=15, leftIndent=16, spaceAfter=3,
        bulletIndent=4)

    label = ParagraphStyle("Label",
        parent=base["Normal"], fontSize=9, textColor=GREY,
        fontName="Helvetica-Bold", spaceAfter=2)

    return title, subtitle, meta, section, body, bullet, label


TITLE_S, SUB_S, META_S, SEC_S, BODY_S, BULL_S, LAB_S = make_styles()


# ── Header banner drawn on every page ───────────────────────
def make_header(canvas, doc):
    canvas.saveState()
    # Dark gradient banner
    canvas.setFillColor(NAVY)
    canvas.rect(0, H - 3.6*cm, W, 3.6*cm, fill=1, stroke=0)
    canvas.setFillColor(BLUE)
    canvas.rect(0, H - 3.7*cm, W, 0.22*cm, fill=1, stroke=0)
    canvas.setFillColor(ACCENT)
    canvas.rect(0, H - 3.92*cm, W, 0.22*cm, fill=1, stroke=0)

    # Footer
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, W, 1.2*cm, fill=1, stroke=0)
    canvas.setFillColor(ACCENT)
    canvas.setFont("Helvetica", 8)
    canvas.drawCentredString(W/2, 0.45*cm,
        "TrafficSense — Multi-Agent Smart City Traffic Management System  |  VIT-AP University  |  Capstone Project 2026-27")
    canvas.setFillColor(GREY)
    canvas.setFont("Helvetica", 7)
    canvas.drawRightString(W - 1.5*cm, 0.45*cm, f"Page {doc.page}")
    canvas.restoreState()


def make_first_page(canvas, doc):
    make_header(canvas, doc)


# ── Helper: coloured section heading ────────────────────────
def sec_heading(text):
    return [
        HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=2),
        Paragraph(f"▌  {text}", SEC_S),
    ]


# ── Helper: info table (2-col key/value) ────────────────────
def info_table(rows):
    data = [[Paragraph(f"<b>{k}</b>", LAB_S), Paragraph(v, BODY_S)] for k, v in rows]
    t = Table(data, colWidths=[4.5*cm, 12.5*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (0,-1), LIGHT),
        ("TEXTCOLOR",  (0,0), (0,-1), NAVY),
        ("ALIGN",      (0,0), (-1,-1), "LEFT"),
        ("VALIGN",     (0,0), (-1,-1), "TOP"),
        ("GRID",       (0,0), (-1,-1), 0.4, BORDER),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [WHITE, colors.HexColor("#F5FBFF")]),
        ("TOPPADDING",  (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1), 5),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
    ]))
    return t


# ── Helper: task/deliverable table ──────────────────────────
def task_table(headers, rows, col_widths):
    header_row = [Paragraph(f"<b>{h}</b>", ParagraphStyle("TH",
        parent=BODY_S, textColor=WHITE, fontName="Helvetica-Bold",
        fontSize=9, alignment=TA_CENTER)) for h in headers]
    data = [header_row]
    for row in rows:
        data.append([Paragraph(str(c), BODY_S) for c in row])
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,0), BLUE),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[WHITE, LIGHT]),
        ("GRID",         (0,0), (-1,-1), 0.4, BORDER),
        ("ALIGN",        (0,0), (-1,-1), "LEFT"),
        ("VALIGN",       (0,0), (-1,-1), "TOP"),
        ("TOPPADDING",   (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1), 5),
        ("LEFTPADDING",  (0,0), (-1,-1), 7),
    ]))
    return t


# ── Badge for completion status ──────────────────────────────
def badge(text, colour=GREEN):
    return Paragraph(
        f'<font color="#{colour.hexval()[2:]}"><b>{text}</b></font>', BODY_S)


# ════════════════════════════════════════════════════════════
#  MEMBER 1 — ACHALLA AKUL LAKHAN   (System Architecture + Multi-Agent)
# ════════════════════════════════════════════════════════════
def report_akul():
    path = os.path.join(OUT_DIR, "23BCE8015_Achalla_Akul_Lakhan.pdf")
    doc = SimpleDocTemplate(path, pagesize=A4,
        topMargin=4.4*cm, bottomMargin=2*cm,
        leftMargin=1.8*cm, rightMargin=1.8*cm)
    story = []

    # ── Header content (printed on banner by canvas) ─────────
    story += [
        Paragraph("INDIVIDUAL CONTRIBUTION REPORT", TITLE_S),
        Paragraph("TrafficSense — Multi-Agent Smart City Traffic Management System", SUB_S),
        Spacer(1, 0.15*cm),
        Paragraph("Capstone Project  |  School of Computer Science &amp; Engineering  |  VIT University", META_S),
        Spacer(1, 1.2*cm),
    ]

    # ── Student Info ─────────────────────────────────────────
    story += sec_heading("Student Information")
    story.append(Spacer(1, 0.3*cm))
    story.append(info_table([
        ("Name",          "Achalla Akul Lakhan"),
        ("Register No.",  "23BCE8015"),
        ("Programme",     "B.Tech — Computer Science and Engineering"),
        ("University",    "VIT-AP University, Amaravati"),
        ("Project Title", "TrafficSense: A Multi-Agent Smart City Traffic Management System"),
        ("Role",          "System Architect &amp; Multi-Agent Systems Lead — responsible for overall project design, LLM-based agent cooperation framework, and CityFlow traffic simulation"),
        ("Academic Year", "FALL SEM 2026-27"),
        ("Faculty Mentor", "Dr. Mohd Irfan, Assistant Professor Sr. Grade-1, SCOPE, VIT-AP University"),
    ]))
    story.append(Spacer(1, 0.4*cm))

    # ── Overview ─────────────────────────────────────────────
    story += sec_heading("Contribution Overview")
    story.append(Paragraph(
        "My primary responsibility in the TrafficSense project was designing the overall system "
        "architecture and implementing the Multi-Agent coordination layer. This is the core "
        "intelligence of the system — the component that makes traffic lights 'talk' to each "
        "other and make cooperative decisions in real time, rather than operating in isolation "
        "on fixed timers.", BODY_S))
    story.append(Spacer(1, 0.3*cm))

    # ── Detailed contributions ────────────────────────────────
    story += sec_heading("Detailed Technical Contributions")

    story.append(Paragraph("<b>1. Overall System Architecture Design</b>", BODY_S))
    for pt in [
        "Designed the three-layer architecture: Perception → Analytics → Multi-Agent Control.",
        "Defined inter-module communication contracts and data schemas (JSON-based state objects).",
        "Established the project directory structure, module boundaries, and integration points.",
        "Created the <i>src/config.py</i> global configuration file used by all modules.",
    ]:
        story.append(Paragraph(f"• {pt}", BULL_S))
    story.append(Spacer(1, 0.2*cm))

    story.append(Paragraph("<b>2. Multi-Agent System (MAS) Framework</b>", BODY_S))
    for pt in [
        "Implemented the agent base class in <i>src/agents/base_agent.py</i> defining the observe → reason → act loop.",
        "Built the intersection agent (<i>src/agents/intersection_agent.py</i>) — each intersection is an autonomous agent that holds its own state and makes local decisions.",
        "Developed the LLM-based reasoning engine: agents query a local LLM (via Ollama) using structured prompts that include real-time congestion data, queue lengths, and neighboring agent states.",
        "Implemented the cooperative communication protocol where agents broadcast their state to direct neighbors and negotiate green-light priorities.",
    ]:
        story.append(Paragraph(f"• {pt}", BULL_S))
    story.append(Spacer(1, 0.2*cm))

    story.append(Paragraph("<b>3. CityFlow Traffic Simulation Integration</b>", BODY_S))
    for pt in [
        "Integrated CityFlow (a high-performance traffic simulator) as the simulation environment.",
        "Built the simulation runner in <i>src/simulation/cityflow_runner.py</i>.",
        "Designed the 4-intersection road network topology with realistic Indian traffic flow parameters.",
        "Implemented the 360-step simulation loop with sub-20-minute execution guarantee.",
        "Wrote the state extractor that converts raw CityFlow output into structured agent observations.",
    ]:
        story.append(Paragraph(f"• {pt}", BULL_S))
    story.append(Spacer(1, 0.2*cm))

    story.append(Paragraph("<b>4. Emergency Vehicle Priority Logic</b>", BODY_S))
    for pt in [
        "Designed and implemented the green corridor algorithm: when the perception layer detects an ambulance, the multi-agent system cascades green signals along the predicted route.",
        "Implemented priority preemption — emergency vehicles override all other scheduling decisions.",
    ]:
        story.append(Paragraph(f"• {pt}", BULL_S))
    story.append(Spacer(1, 0.3*cm))

    # ── Deliverables table ────────────────────────────────────
    story += sec_heading("Deliverables & Files")
    story.append(task_table(
        ["File / Module", "Description", "Status"],
        [
            ["src/config.py",                     "Global project configuration",                    "✔ Complete"],
            ["src/agents/base_agent.py",           "Abstract agent base class",                       "✔ Complete"],
            ["src/agents/intersection_agent.py",   "LLM-driven intersection controller",              "✔ Complete"],
            ["src/agents/coordinator.py",          "Multi-agent coordinator and message broker",      "✔ Complete"],
            ["src/simulation/cityflow_runner.py",  "CityFlow simulation harness (360 steps)",         "✔ Complete"],
            ["src/simulation/state_extractor.py",  "Converts simulation state to agent observations", "✔ Complete"],
            ["data/cityflow/",                     "Road network JSON configs for 4 intersections",   "✔ Complete"],
        ],
        [7*cm, 7.5*cm, 2.5*cm]
    ))
    story.append(Spacer(1, 0.4*cm))

    # ── Technologies ──────────────────────────────────────────
    story += sec_heading("Technologies & Tools Used")
    story.append(info_table([
        ("Language",      "Python 3.12"),
        ("Simulation",    "CityFlow (C++ traffic simulator with Python API)"),
        ("LLM Engine",    "Ollama (local LLM inference) + structured JSON prompting"),
        ("Agent Logic",   "Custom rule-based + LLM hybrid reasoning"),
        ("Config",        "YAML / JSON"),
        ("Version Control","Git + GitHub"),
    ]))
    story.append(Spacer(1, 0.4*cm))

    # ── Declaration ───────────────────────────────────────────
    story += sec_heading("Declaration")
    story.append(Paragraph(
        "I, Achalla Akul Lakhan (23BCE8015), hereby declare that the contributions described in "
        "this report are my individual work carried out as part of the TrafficSense Capstone "
        "Project. All implementations listed above were personally designed, coded, tested, and "
        "integrated by me.", BODY_S))
    story.append(Spacer(1, 0.6*cm))
    story.append(Paragraph("Signature: ____________________________    Date: ____________", BODY_S))

    doc.build(story, onFirstPage=make_first_page, onLaterPages=make_header)
    print(f"  ✔  {path}")


# ════════════════════════════════════════════════════════════
#  MEMBER 2 — C BHARGAV KUMAR   (YOLOv8 + Vision + Training)
# ════════════════════════════════════════════════════════════
def report_bhargav():
    path = os.path.join(OUT_DIR, "23BCE8195_C_Bhargav_Kumar.pdf")
    doc = SimpleDocTemplate(path, pagesize=A4,
        topMargin=4.4*cm, bottomMargin=2*cm,
        leftMargin=1.8*cm, rightMargin=1.8*cm)
    story = []

    story += [
        Paragraph("INDIVIDUAL CONTRIBUTION REPORT", TITLE_S),
        Paragraph("TrafficSense — Multi-Agent Smart City Traffic Management System", SUB_S),
        Spacer(1, 0.15*cm),
        Paragraph("Capstone Project  |  School of Computer Science &amp; Engineering  |  VIT University", META_S),
        Spacer(1, 1.2*cm),
    ]

    story += sec_heading("Student Information")
    story.append(Spacer(1, 0.3*cm))
    story.append(info_table([
        ("Name",          "C Bhargav Kumar"),
        ("Register No.",  "23BCE8195"),
        ("Programme",     "B.Tech — Computer Science and Engineering"),
        ("University",    "VIT-AP University, Amaravati"),
        ("Project Title", "TrafficSense: A Multi-Agent Smart City Traffic Management System"),
        ("Role",          "Computer Vision &amp; ML Lead — responsible for YOLOv8 model training, custom Indian dataset creation, augmentation pipeline, and real-time inference integration"),
        ("Academic Year", "FALL SEM 2026-27"),
        ("Faculty Mentor", "Dr. Mohd Irfan, Assistant Professor Sr. Grade-1, SCOPE, VIT-AP University"),
    ]))
    story.append(Spacer(1, 0.4*cm))

    story += sec_heading("Contribution Overview")
    story.append(Paragraph(
        "My primary responsibility was the entire Computer Vision and Machine Learning pipeline. "
        "This includes selecting the detection model, building the custom Indian traffic dataset, "
        "designing and executing all training runs, integrating YOLO-World for zero-shot detection, "
        "and deploying the final model into the live inference pipeline. The model I trained "
        "achieves a final mAP50 of <b>70.5%</b> with auto-rickshaw detection at <b>99.5% accuracy</b> "
        "— a class that standard COCO models cannot detect at all.", BODY_S))
    story.append(Spacer(1, 0.3*cm))

    story += sec_heading("Detailed Technical Contributions")

    story.append(Paragraph("<b>1. Model Selection &amp; Architecture</b>", BODY_S))
    for pt in [
        "Evaluated YOLOv8n, YOLOv8s, and YOLOv8m variants for accuracy vs. VRAM trade-off on the RTX 4050 6GB GPU.",
        "Selected YOLOv8m (25M parameters) as the final model — provides significantly better accuracy than YOLOv8s while fitting within 6GB VRAM at 640px.",
        "Integrated YOLO-World (open-vocabulary zero-shot model) as an alternate detection engine allowing text-based class specification.",
    ]:
        story.append(Paragraph(f"• {pt}", BULL_S))
    story.append(Spacer(1, 0.2*cm))

    story.append(Paragraph("<b>2. Custom Indian Traffic Dataset Creation</b>", BODY_S))
    for pt in [
        "Defined a comprehensive 24-class taxonomy specific to Indian roads: car, motorcycle, bus, truck, autorickshaw, bicycle, ambulance, police_vehicle, tractor, pedestrian, traffic_light, traffic_sign, scooter, e-rickshaw, van, tempo, animal, pushcart, water_tanker, excavator, crane, jeep, mini_bus, fire_engine.",
        "Sourced and labeled images from multiple Indian traffic datasets and integrated them into a unified YOLO-format dataset.",
        "Used Roboflow API to download and merge 4 additional Indian traffic datasets, growing the corpus to 42,652 training images after augmentation.",
        "Wrote the class remapping pipeline (src/perception/download_datasets.py) to normalise heterogeneous class names from different sources into our 24-class scheme.",
    ]:
        story.append(Paragraph(f"• {pt}", BULL_S))
    story.append(Spacer(1, 0.2*cm))

    story.append(Paragraph("<b>3. Data Augmentation Pipeline</b>", BODY_S))
    for pt in [
        "Built a heavy augmentation pipeline (src/perception/augment_dataset.py) using the Albumentations library.",
        "Applied 10+ augmentation strategies: random fog, simulated rain, ISO noise, motion blur, perspective warp, brightness/contrast variation, and HSV shifts — simulating Indian monsoon and night driving conditions.",
        "Multiplied the base dataset ×15, converting ~2,840 raw images into 42,652 synthetic training variants.",
    ]:
        story.append(Paragraph(f"• {pt}", BULL_S))
    story.append(Spacer(1, 0.2*cm))

    story.append(Paragraph("<b>4. Model Training — Nuclear Run + Fine-Tuning</b>", BODY_S))
    for pt in [
        "Executed a large-scale nuclear training run on 42,652 images at 832px resolution (YOLOv8m, AdamW optimizer, 9 full epochs = 380,000+ image passes).",
        "Designed and executed a targeted fine-tuning stage (src/perception/fast_finetune.py) from the pre-trained checkpoint on a curated 1,500-image balanced subset at 640px.",
        "Achieved early stopping at epoch 57 (patience=30), with best weights saved at epoch 27.",
        "Final model performance: <b>mAP50 = 70.5%, mAP50-95 = 67.4%</b>, auto-rickshaw mAP50 = 99.5%.",
        "Auto-deployed best.pt to models/yolo/best.pt for direct use by the dashboard.",
    ]:
        story.append(Paragraph(f"• {pt}", BULL_S))
    story.append(Spacer(1, 0.2*cm))

    story.append(Paragraph("<b>5. Inference Pipeline</b>", BODY_S))
    for pt in [
        "Built the real-time inference pipeline (src/perception/inference_pipeline.py) supporting both file-based and live webcam inputs.",
        "Integrated ByteTrack multi-object tracking to assign persistent vehicle IDs across frames.",
        "Built the CongestionAnalyzer module to convert per-frame detections into congestion scores.",
    ]:
        story.append(Paragraph(f"• {pt}", BULL_S))
    story.append(Spacer(1, 0.3*cm))

    story += sec_heading("Training Results Summary")
    story.append(task_table(
        ["Class", "mAP50", "Precision", "Recall"],
        [
            ["All Classes (Average)", "70.5%", "76.2%", "61.4%"],
            ["Car",             "78.7%", "86.1%", "75.0%"],
            ["Auto-rickshaw",   "99.5%", "62.8%", "100%"],
            ["Bus",             "99.5%", "50.1%", "100%"],
            ["Pedestrian",      "99.5%", "90.9%", "100%"],
            ["Police Vehicle",  "99.5%", "61.8%", "100%"],
            ["Van",             "99.5%", "100%",  "—"],
        ],
        [5.5*cm, 3.5*cm, 3.5*cm, 4.5*cm]
    ))
    story.append(Spacer(1, 0.4*cm))

    story += sec_heading("Deliverables & Files")
    story.append(task_table(
        ["File / Module", "Description", "Status"],
        [
            ["src/perception/train_yolo.py",        "Primary YOLOv8 training script",              "✔ Complete"],
            ["src/perception/fast_finetune.py",      "Targeted fine-tuning from checkpoint",        "✔ Complete"],
            ["src/perception/augment_dataset.py",    "Albumentations augmentation pipeline",        "✔ Complete"],
            ["src/perception/download_datasets.py",  "Roboflow multi-dataset downloader",           "✔ Complete"],
            ["src/perception/full_pipeline.py",      "End-to-end data → train pipeline",            "✔ Complete"],
            ["src/perception/inference_pipeline.py", "Real-time YOLOv8 inference + tracking",       "✔ Complete"],
            ["src/perception/tracker.py",            "ByteTrack vehicle tracker",                   "✔ Complete"],
            ["src/perception/congestion_analyzer.py","Congestion level computation",                "✔ Complete"],
            ["models/yolo/best.pt",                  "Trained model weights (52MB, YOLOv8m)",       "✔ Deployed"],
            ["data/processed/unified_indian/",       "Custom 24-class Indian traffic dataset",      "✔ Complete"],
        ],
        [6.5*cm, 7.5*cm, 2.5*cm]
    ))
    story.append(Spacer(1, 0.4*cm))

    story += sec_heading("Technologies & Tools Used")
    story.append(info_table([
        ("Framework",        "Ultralytics YOLOv8 (v8.4.129)"),
        ("Model",            "YOLOv8m — 25.8M parameters, 79.1 GFLOPs"),
        ("Zero-Shot Model",  "YOLO-World with CLIP embeddings"),
        ("Augmentation",     "Albumentations v1.x"),
        ("Dataset Platform", "Roboflow Universe API"),
        ("Hardware",         "NVIDIA GeForce RTX 4050 Laptop (6GB VRAM), CUDA 12.1"),
        ("Language",         "Python 3.12, PyTorch 2.5.1"),
        ("Training Time",    "~18 hours total (nuclear run + fine-tune)"),
    ]))
    story.append(Spacer(1, 0.4*cm))

    story += sec_heading("Declaration")
    story.append(Paragraph(
        "I, C Bhargav Kumar (23BCE8195), hereby declare that the contributions described in this "
        "report — including model selection, dataset construction, augmentation pipeline, all "
        "training runs, and inference integration — are my individual work carried out as part of "
        "the TrafficSense Capstone Project.", BODY_S))
    story.append(Spacer(1, 0.6*cm))
    story.append(Paragraph("Signature: ____________________________    Date: ____________", BODY_S))

    doc.build(story, onFirstPage=make_first_page, onLaterPages=make_header)
    print(f"  ✔  {path}")


# ════════════════════════════════════════════════════════════
#  MEMBER 3 — DARSI AMIT   (Dashboard / Frontend / UI)
# ════════════════════════════════════════════════════════════
def report_amit():
    path = os.path.join(OUT_DIR, "23BCE8288_Darsi_Amit.pdf")
    doc = SimpleDocTemplate(path, pagesize=A4,
        topMargin=4.4*cm, bottomMargin=2*cm,
        leftMargin=1.8*cm, rightMargin=1.8*cm)
    story = []

    story += [
        Paragraph("INDIVIDUAL CONTRIBUTION REPORT", TITLE_S),
        Paragraph("TrafficSense — Multi-Agent Smart City Traffic Management System", SUB_S),
        Spacer(1, 0.15*cm),
        Paragraph("Capstone Project  |  School of Computer Science &amp; Engineering  |  VIT University", META_S),
        Spacer(1, 1.2*cm),
    ]

    story += sec_heading("Student Information")
    story.append(Spacer(1, 0.3*cm))
    story.append(info_table([
        ("Name",          "Darsi Amit"),
        ("Register No.",  "23BCE8288"),
        ("Programme",     "B.Tech — Computer Science and Engineering"),
        ("University",    "VIT-AP University, Amaravati"),
        ("Project Title", "TrafficSense: A Multi-Agent Smart City Traffic Management System"),
        ("Role",          "Frontend &amp; Dashboard Lead — responsible for the complete Streamlit multi-page dashboard, CSS theming, live detection UI, and Plotly analytics visualisations"),
        ("Academic Year", "FALL SEM 2026-27"),
        ("Faculty Mentor", "Dr. Mohd Irfan, Assistant Professor Sr. Grade-1, SCOPE, VIT-AP University"),
    ]))
    story.append(Spacer(1, 0.4*cm))

    story += sec_heading("Contribution Overview")
    story.append(Paragraph(
        "My primary responsibility was designing and building the complete real-time web dashboard "
        "for the TrafficSense system. This includes all four Streamlit pages, the custom CSS "
        "glassmorphism theme, interactive Plotly charts, the live video detection interface, and "
        "the real-time agent cooperation visualisation. The dashboard serves as the primary "
        "interface for city planners and faculty to interact with and demonstrate the system.", BODY_S))
    story.append(Spacer(1, 0.3*cm))

    story += sec_heading("Detailed Technical Contributions")

    story.append(Paragraph("<b>1. Dashboard Architecture &amp; Theming</b>", BODY_S))
    for pt in [
        "Designed and implemented the multi-page Streamlit dashboard using Streamlit's native Page navigation API.",
        "Created a comprehensive glassmorphism CSS theme (src/dashboard/utils.py) with Google Inter fonts, gradient buttons, pulsing animations, and glowing metric cards.",
        "Implemented st.html() rendering to inject complex HTML/CSS components without Streamlit's markdown parser interfering.",
        "Built reusable component library: metric_card.py and intersection_card.py for consistent UI across pages.",
    ]:
        story.append(Paragraph(f"• {pt}", BULL_S))
    story.append(Spacer(1, 0.2*cm))

    story.append(Paragraph("<b>2. Landing Page (app.py)</b>", BODY_S))
    for pt in [
        "Designed the Hero section with animated gradient headline and project tagline.",
        "Built responsive 4-column metric grid showing live system-wide statistics.",
        "Created visual navigation cards with icons and descriptions for each dashboard section.",
        "Added a Model Health status card showing the current AI model's mAP, training date, and active classes.",
    ]:
        story.append(Paragraph(f"• {pt}", BULL_S))
    story.append(Spacer(1, 0.2*cm))

    story.append(Paragraph("<b>3. Live Traffic Monitor (pages/1_live_monitor.py)</b>", BODY_S))
    for pt in [
        "Built the complete video upload and real-time YOLO inference interface.",
        "Implemented a three-mode model selector: Custom Indian (24 classes), COCO Pretrained (80 classes), and YOLO-World (Open Vocabulary) with a live text-input class selector.",
        "Designed the side-by-side layout: video feed on the left, live telemetry metrics panel on the right.",
        "Integrated real-time glowing metric cards showing Active Entities, Congestion Level, Avg Confidence, and Processing FPS.",
        "Built the post-processing analytics section with vehicle class distribution bar chart.",
    ]:
        story.append(Paragraph(f"• {pt}", BULL_S))
    story.append(Spacer(1, 0.2*cm))

    story.append(Paragraph("<b>4. Network Control Centre (pages/2_network_control.py)</b>", BODY_S))
    for pt in [
        "Created a 2×2 visual intersection grid representing the physical 4-intersection road network.",
        "Implemented LED-style glowing dot indicators showing current traffic light phase (Red/Yellow/Green) for each intersection.",
        "Built the Cooperative Reasoning Log — a live scrolling feed of LLM agent decision messages.",
        "Designed the Agent Cooperation Map showing message flow between intersections.",
    ]:
        story.append(Paragraph(f"• {pt}", BULL_S))
    story.append(Spacer(1, 0.2*cm))

    story.append(Paragraph("<b>5. Analytics Page (pages/3_analytics.py)</b>", BODY_S))
    for pt in [
        "Built a full analytics suite using Plotly with the dark theme.",
        "Implemented comparative charts: TrafficSense vs. Fixed Timer vs. Random baseline.",
        "Created the Executive Summary table showing % improvement in wait time, queue length, and throughput.",
        "Embedded training performance visualisations (confusion matrix, F1 curves) from the YOLOv8 training outputs.",
    ]:
        story.append(Paragraph(f"• {pt}", BULL_S))
    story.append(Spacer(1, 0.3*cm))

    story += sec_heading("Deliverables & Files")
    story.append(task_table(
        ["File / Module", "Description", "Status"],
        [
            ["src/dashboard/app.py",                  "Landing page — Hero, metrics, navigation",      "✔ Complete"],
            ["src/dashboard/utils.py",                 "Global CSS theme + helper functions",           "✔ Complete"],
            ["src/dashboard/pages/1_live_monitor.py",  "Live YOLO detection interface",                 "✔ Complete"],
            ["src/dashboard/pages/2_network_control.py","Intersection grid + agent cooperation log",    "✔ Complete"],
            ["src/dashboard/pages/3_analytics.py",     "Plotly charts + executive summary",            "✔ Complete"],
            ["src/dashboard/components/metric_card.py","Reusable glowing metric card component",       "✔ Complete"],
            ["src/dashboard/components/intersection_card.py","Intersection LED status card",           "✔ Complete"],
        ],
        [6.5*cm, 7.5*cm, 2.5*cm]
    ))
    story.append(Spacer(1, 0.4*cm))

    story += sec_heading("Technologies & Tools Used")
    story.append(info_table([
        ("Framework",      "Streamlit v1.45.1"),
        ("Charts",         "Plotly v5.x (dark theme)"),
        ("Styling",        "Custom CSS — Glassmorphism, Google Inter Font, CSS animations"),
        ("HTML Rendering", "st.html() native Streamlit API"),
        ("Video Processing","OpenCV + Streamlit video display"),
        ("Language",       "Python 3.12"),
        ("Port",           "8505 (localhost)"),
    ]))
    story.append(Spacer(1, 0.4*cm))

    story += sec_heading("Declaration")
    story.append(Paragraph(
        "I, Darsi Amit (23BCE8288), hereby declare that the contributions described in this "
        "report — including the full Streamlit dashboard design, all four pages, CSS theming, "
        "component library, and Plotly visualisations — are my individual work carried out as "
        "part of the TrafficSense Capstone Project.", BODY_S))
    story.append(Spacer(1, 0.6*cm))
    story.append(Paragraph("Signature: ____________________________    Date: ____________", BODY_S))

    doc.build(story, onFirstPage=make_first_page, onLaterPages=make_header)
    print(f"  ✔  {path}")


# ════════════════════════════════════════════════════════════
#  MEMBER 4 — MYLAPALLI ABHISHEK RAJ   (Data Pipeline + Integration + Testing)
# ════════════════════════════════════════════════════════════
def report_abhishek():
    path = os.path.join(OUT_DIR, "23BCE9470_Mylapalli_Abhishek_Raj.pdf")
    doc = SimpleDocTemplate(path, pagesize=A4,
        topMargin=4.4*cm, bottomMargin=2*cm,
        leftMargin=1.8*cm, rightMargin=1.8*cm)
    story = []

    story += [
        Paragraph("INDIVIDUAL CONTRIBUTION REPORT", TITLE_S),
        Paragraph("TrafficSense — Multi-Agent Smart City Traffic Management System", SUB_S),
        Spacer(1, 0.15*cm),
        Paragraph("Capstone Project  |  School of Computer Science &amp; Engineering  |  VIT University", META_S),
        Spacer(1, 1.2*cm),
    ]

    story += sec_heading("Student Information")
    story.append(Spacer(1, 0.3*cm))
    story.append(info_table([
        ("Name",          "Mylapalli Abhishek Raj"),
        ("Register No.",  "23BCE9470"),
        ("Programme",     "B.Tech — Computer Science and Engineering"),
        ("University",    "VIT-AP University, Amaravati"),
        ("Project Title", "TrafficSense: A Multi-Agent Smart City Traffic Management System"),
        ("Role",          "Data Engineering &amp; Integration Lead — responsible for dataset collection, preprocessing pipeline, cross-module system integration, testing, and project documentation"),
        ("Academic Year", "FALL SEM 2026-27"),
        ("Faculty Mentor", "Dr. Mohd Irfan, Assistant Professor Sr. Grade-1, SCOPE, VIT-AP University"),
    ]))
    story.append(Spacer(1, 0.4*cm))

    story += sec_heading("Contribution Overview")
    story.append(Paragraph(
        "My primary responsibility spanned two critical areas: (1) building the raw data collection "
        "and preprocessing pipeline that feeds the entire machine learning system, and (2) "
        "integrating all independent modules (perception, simulation, agents, dashboard) into a "
        "coherent, working system. I also owned all testing, verification, and documentation "
        "efforts for the project.", BODY_S))
    story.append(Spacer(1, 0.3*cm))

    story += sec_heading("Detailed Technical Contributions")

    story.append(Paragraph("<b>1. Dataset Research &amp; Raw Data Collection</b>", BODY_S))
    for pt in [
        "Conducted systematic literature review to identify suitable Indian traffic datasets: IDD (Indian Driving Dataset), DriveIndia, DATS-2022, and Roboflow Universe collections.",
        "Evaluated each dataset for class coverage, annotation quality, image diversity, and licensing compatibility.",
        "Authored the data acquisition documentation and README files in data/raw/ directories.",
        "Managed the Roboflow API integration process and obtained the team's API credentials.",
    ]:
        story.append(Paragraph(f"• {pt}", BULL_S))
    story.append(Spacer(1, 0.2*cm))

    story.append(Paragraph("<b>2. Data Preprocessing Pipeline</b>", BODY_S))
    for pt in [
        "Built src/perception/data_pipeline.py — a complete preprocessing pipeline converting raw multi-format annotations (Pascal VOC XML, COCO JSON) into YOLO TXT format.",
        "Implemented dataset splitting logic (70% train / 20% val / 10% test) with stratified sampling to ensure class balance.",
        "Wrote the dataset verification script (tests/verify_datasets.py) to check for corrupt images, missing labels, and class distribution statistics.",
        "Curated the final unified Indian dataset (data/processed/unified_indian/) — the standardised dataset used for all training.",
    ]:
        story.append(Paragraph(f"• {pt}", BULL_S))
    story.append(Spacer(1, 0.2*cm))

    story.append(Paragraph("<b>3. System Integration</b>", BODY_S))
    for pt in [
        "Designed and implemented the end-to-end integration between the perception layer (YOLO) and the multi-agent control layer.",
        "Built src/perception/convert_real_states.py — converts raw YOLO detection outputs into structured CityFlow-compatible state vectors for the agent system.",
        "Resolved all cross-module import path issues (sys.path management, PROJECT_ROOT resolution across all dashboard pages).",
        "Implemented the mock Ollama server (tests/mock_ollama.py) for testing agent LLM calls without requiring a live LLM service.",
        "Ensured all modules share a single unified configuration (src/config.py) — no hardcoded paths.",
    ]:
        story.append(Paragraph(f"• {pt}", BULL_S))
    story.append(Spacer(1, 0.2*cm))

    story.append(Paragraph("<b>4. Testing &amp; Quality Assurance</b>", BODY_S))
    for pt in [
        "Wrote and maintained the full test suite under tests/ covering dataset validation, model loading, agent state transitions, and simulation step execution.",
        "Performed end-to-end integration tests: uploaded test videos to the dashboard and verified detection accuracy across all three model modes.",
        "Identified and documented 12+ bugs across the codebase during the audit phase, including encoding errors, path resolution bugs, and Streamlit API deprecations.",
        "Validated that the CityFlow simulation completes 360 steps in under 20 minutes.",
    ]:
        story.append(Paragraph(f"• {pt}", BULL_S))
    story.append(Spacer(1, 0.2*cm))

    story.append(Paragraph("<b>5. Documentation &amp; Deployment</b>", BODY_S))
    for pt in [
        "Authored the project README.md with complete setup, installation, and usage instructions.",
        "Managed all Git commits, branch strategy, and GitHub repository maintenance throughout the project.",
        "Wrote requirements.txt and ensured reproducible environment setup.",
        "Maintained the implementation plan and tracked progress against milestones.",
    ]:
        story.append(Paragraph(f"• {pt}", BULL_S))
    story.append(Spacer(1, 0.3*cm))

    story += sec_heading("Deliverables & Files")
    story.append(task_table(
        ["File / Module", "Description", "Status"],
        [
            ["src/perception/data_pipeline.py",     "Raw data preprocessing + format conversion",  "✔ Complete"],
            ["src/perception/convert_real_states.py","Detection → agent state converter",           "✔ Complete"],
            ["tests/verify_datasets.py",             "Dataset health check script",                 "✔ Complete"],
            ["tests/mock_ollama.py",                 "Mock LLM server for offline testing",         "✔ Complete"],
            ["tests/test_integration.py",            "End-to-end integration test suite",           "✔ Complete"],
            ["data/processed/unified_indian/",       "Curated, split, verified training dataset",   "✔ Complete"],
            ["README.md",                            "Full project setup and usage documentation",  "✔ Complete"],
            ["requirements.txt",                     "Reproducible Python dependency list",         "✔ Complete"],
        ],
        [6.5*cm, 7.5*cm, 2.5*cm]
    ))
    story.append(Spacer(1, 0.4*cm))

    story += sec_heading("Technologies & Tools Used")
    story.append(info_table([
        ("Language",        "Python 3.12"),
        ("Data Formats",    "YOLO TXT, Pascal VOC XML, COCO JSON"),
        ("Testing",         "Python unittest + custom integration scripts"),
        ("Documentation",   "Markdown (README, inline docstrings)"),
        ("Version Control", "Git + GitHub (branch management, PR reviews)"),
        ("Dataset Platform","Roboflow Universe, Kaggle, IDD Portal"),
        ("Environment",     "Windows 11 + WSL2 Ubuntu 22.04"),
    ]))
    story.append(Spacer(1, 0.4*cm))

    story += sec_heading("Declaration")
    story.append(Paragraph(
        "I, Mylapalli Abhishek Raj (23BCE9470), hereby declare that the contributions described "
        "in this report — including raw data collection, preprocessing pipeline, system "
        "integration, testing, and documentation — are my individual work carried out as part of "
        "the TrafficSense Capstone Project.", BODY_S))
    story.append(Spacer(1, 0.6*cm))
    story.append(Paragraph("Signature: ____________________________    Date: ____________", BODY_S))

    doc.build(story, onFirstPage=make_first_page, onLaterPages=make_header)
    print(f"  ✔  {path}")


# ── Run all ──────────────────────────────────────────────────
if __name__ == "__main__":
    print("\nGenerating Individual Contribution Reports...\n")
    report_akul()
    report_bhargav()
    report_amit()
    report_abhishek()
    print(f"\nAll 4 reports saved to: {OUT_DIR}\n")
