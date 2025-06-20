# 🗃️ SomethingAwful Thread Archiver

Note: This is vibe coded crap, but it works

## 🚀 Quick Start

### Docker Compose**
```bash
git clone <repository-url>
cd SA-Archiver
docker-compose up --build
```

## 🌐 Web Interface

Access the application at `http://localhost:5000`

### **Main Pages:**
- **`/`** - Landing page with feature overview
- **`/archive`** - Main archiving interface
- **`/json`** - Convert HTML archives to JSON
- **`/standalone`** - Generate standalone HTML files

## 💾 Output Structure

### **Full Page Mode:**
```
output/
└── thread_name/
    ├── showthread.php@threadid=12345&pagenumber=1.html
    ├── showthread.php@threadid=12345&pagenumber=2.html
    ├── image1.jpg
    ├── image2.png
    └── ...
```

### **Images Only Mode:**
```
output/
└── thread_name/
    └── images/
        ├── _download_summary.txt
        ├── funny_meme.jpg
        ├── attachment_abc123.pdf
        ├── avatar_def456.png
        └── ...
```

### **JSON Mode:**
```
output/
└── thread_name/
    ├── json/
    │   ├── 1.json
    │   ├── 2.json
    │   └── ...
    └── standalone.html
```

## 🛠️ Usage Guide

### **Archiving a Thread:**
1. Navigate to `/archive`
2. Enter the thread URL (first page)
3. Set start/end page numbers
4. Choose download mode:
   - **Full page**: Complete HTML + images
   - **Images only**: Just images with duplicate prevention
5. Enter SA credentials (saved automatically)
6. Click "Start Download"

If only downloading images, you're done!

### **Converting to JSON:**
1. Archive thread using full page mode
2. Navigate to `/json`
3. Select your archived folder
4. Convert HTML to structured JSON format

### **Creating Standalone Files:**
1. Convert thread to JSON first
2. Navigate to `/standalone`
3. Generate self-contained HTML file with embedded styles

### **Upload the folder to a hosting service!**