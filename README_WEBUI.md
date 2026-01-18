# FFXI Gear Set Optimizer - Web UI

A web-based interface for the FFXI Gear Set Optimizer that uses beam search and wsdist simulation to find optimal gear configurations.

## Features

- **TP Set Optimization**: Find the best gear for TP accumulation
  - Pure TP (maximum TP rate)
  - Hybrid TP (balance TP with damage)
  - Accuracy TP (for tough content)
  - DT TP (survivability + TP)
  - Refresh TP (MP sustain for mages)

- **WS Set Optimization**: Optimize gear for weaponskill damage
  - Supports all physical, magical, and hybrid weaponskills
  - Considers stat modifiers, fTP, multi-attack, etc.

- **DT Set Optimization**: Find gear for damage reduction
  - General DT, Physical DT, Magical DT priorities

- **Inventory Browser**: View and search your loaded gear

## Requirements

- Python 3.10+
- Required packages (install via pip):
  ```bash
  pip install fastapi pydantic uvicorn python-multipart numba numpy
  ```

## Quick Start

1. **Start the server:**
   ```bash
   python start_server.py
   ```
   
   Or with options:
   ```bash
   python start_server.py --port 8080 --host 0.0.0.0
   ```

2. **Open your browser** and navigate to:
   ```
   http://localhost:8000
   ```

3. **Upload your inventory:**
   - Click "Upload Data" in the header
   - Upload your `inventory_*.csv` file (from Ashita/Windower plugin)
   - Optionally upload your `jobgifts_*.csv` file for JP bonuses

4. **Configure and optimize:**
   - Select your job
   - Select your main weapon and off-hand
   - Choose a weaponskill (for WS optimization)
   - Configure buffs and target enemy
   - Click "Optimize" to run the optimization

5. **View results:**
   - Results appear in the right panel
   - Click on a result to see full gear details
   - Copy the generated Lua code for GearSwap

## API Documentation

The FastAPI backend provides automatic API documentation:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## File Structure

```
GSO_wsdist/
├── api.py              # FastAPI backend
├── start_server.py     # Startup script
├── static/
│   ├── index.html      # Main web page
│   ├── css/
│   │   └── app.css     # Custom styles
│   └── js/
│       └── app.js      # Frontend JavaScript
├── optimizer_ui.py     # Original terminal UI
├── beam_search_optimizer.py
├── models.py
├── inventory_loader.py
├── ws_database.py
└── wsdist_beta-main/   # wsdist simulation engine
```

## Tips

- **Master Level**: If your job has 2100+ JP, you can set your Master Level (0-50) for additional stat bonuses.

- **Dual Wield**: Check "Has Dual Wield" if you have DW from /NIN, /DNC, or gear. This affects TP set optimization.

- **Target Selection**: Choose a target that matches the content you're optimizing for. Defense and evasion values significantly affect the results.

- **Buffs**: Add the buffs you typically have available. Haste is particularly important for TP sets.

## Troubleshooting

**Server won't start:**
- Make sure all dependencies are installed
- Check if port 8000 is already in use (try `--port 8080`)

**"No inventory loaded" error:**
- Upload your inventory CSV file before running optimizations

**wsdist unavailable:**
- Install numba: `pip install numba`
- Optimization will still work (beam search only) but won't have accurate damage simulations

## Credits

- **wsdist**: Damage simulation engine by Kastra (Asura)
- **Gear data**: From FFXI item database
- **Web UI**: Built with FastAPI, Tailwind CSS
