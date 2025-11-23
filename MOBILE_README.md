# Wood Cut Optimizer - Mobile Companion App

A lightweight mobile web companion for the Wood Cut Optimizer desktop application.

## Features

- ✅ Mobile-optimized responsive design
- ✅ Works on any smartphone browser (iOS, Android)
- ✅ Same optimization algorithm as desktop app
- ✅ Touch-friendly interface
- ✅ Visual cutting diagrams
- ✅ Shopping list generation
- ✅ No app store needed - works in browser

## Quick Start

### 1. Install Dependencies

```bash
pip install flask
```

(Note: The app reuses the optimization logic, so no need for reportlab or tkinter)

### 2. Run the Server

```bash
python mobile_app.py
```

The server will start on `http://0.0.0.0:5000`

### 3. Access from Mobile Device

**On the same WiFi network:**

1. Find your computer's IP address:
   - Windows: `ipconfig` → look for "IPv4 Address"
   - Mac/Linux: `ifconfig` or `ip addr` → look for your local IP (e.g., 192.168.1.100)

2. On your phone, open a browser and go to:
   ```
   http://YOUR_COMPUTER_IP:5000
   ```
   Example: `http://192.168.1.100:5000`

3. Bookmark it for easy access!

**Optional: Add to Home Screen (iOS/Android)**
- iOS Safari: Tap Share → Add to Home Screen
- Android Chrome: Menu → Add to Home screen

## How to Use

1. **Set Units**: Choose inches or centimeters
2. **Add Stock Boards**: Define your available board sizes
3. **Add Pieces**: Enter pieces you need to cut
4. **Optimize**: Tap "Calculate Optimization"
5. **View Results**: See shopping list and cutting plans

## Features Comparison

| Feature | Desktop App | Mobile Companion |
|---------|------------|------------------|
| Optimization | ✅ Full | ✅ Full |
| Shopping List | ✅ | ✅ |
| Visual Diagrams | ✅ PDF | ✅ Canvas |
| Save/Load Projects | ✅ JSON | ❌ |
| PDF Export | ✅ | ❌ |
| Keyboard Shortcuts | ✅ | ❌ |
| Offline Use | ✅ | ❌ (needs server) |

## Deployment Options

### For Personal Use (Local Network)
Just run `python mobile_app.py` and access from your phone on WiFi.

### For Public Access
Deploy to a platform like:
- **Heroku** (free tier)
- **PythonAnywhere** (free tier)
- **AWS/DigitalOcean** (paid)
- **Render** (free tier)

Example Heroku deployment:
```bash
# Create Procfile
echo "web: python mobile_app.py" > Procfile

# Create requirements.txt
echo "flask==3.0.0" > requirements.txt

# Deploy
git init
heroku create wood-cut-optimizer
git add .
git commit -m "Deploy mobile app"
git push heroku main
```

## Differences from Desktop

**Simplified Features:**
- No project save/load (lightweight for mobile)
- No PDF export (view on screen instead)
- Optimized for touch input
- Smaller canvas visualizations

**Shared Core:**
- ✅ Same bin packing algorithm
- ✅ Same optimization quality
- ✅ Same calculation accuracy

## Troubleshooting

**Can't connect from phone?**
- Make sure phone and computer are on same WiFi
- Check firewall isn't blocking port 5000
- Try `python mobile_app.py` with `host='0.0.0.0'` (already set)

**Optimization fails?**
- Check that all required fields are filled
- Ensure pieces fit on selected boards
- Verify buffer/kerf value is reasonable

**Canvas doesn't show?**
- Some older browsers may not support HTML5 Canvas
- Try Chrome or Safari on mobile

## Technical Details

- **Backend**: Flask (Python)
- **Frontend**: Vanilla JavaScript + HTML5 Canvas
- **Styling**: Mobile-first responsive CSS
- **Algorithm**: Maximal Rectangles bin packing
- **Storage**: Session-only (no database needed)

## License

Same as desktop application.
