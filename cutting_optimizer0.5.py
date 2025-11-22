#!/usr/bin/env python3
"""
Wood Cutting Optimization Application
Optimizes cutting patterns for wood pieces from larger stock boards
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import math
from dataclasses import dataclass, asdict
from typing import List, Tuple, Optional, Dict
from datetime import datetime
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_CENTER, TA_LEFT


# Modern dark mode color scheme
DARK_BG = "#1e1e1e"              # Main background
DARK_FG = "#e4e4e4"              # Main text
DARK_INPUT_BG = "#2d2d2d"        # Input fields
DARK_INPUT_FG = "#cccccc"        # Input text
DARK_BUTTON_BG = "#3a3a3a"       # Button background
DARK_BUTTON_FG = "#ffffff"       # Button text
DARK_SELECT_BG = "#094771"       # Selection/hover
DARK_BORDER = "#3e3e3e"          # Borders
DARK_NOTEBOOK_BG = "#252526"     # Tab background
DARK_ACCENT = "#0e7afa"          # Accent color (modern blue)
DARK_SUCCESS = "#16c60c"         # Success/validation green
DARK_ERROR = "#f14c4c"           # Error/validation red
DARK_WARNING = "#cca700"         # Warning yellow
DARK_PANEL = "#252526"           # Panel/section background

# Application metadata
APP_NAME = "Wood Cut Optimizer"
APP_VERSION = "1.0"
APP_AUTHOR = "Woodworking Solutions"


@dataclass
class StockBoard:
    """Represents an uncut stock board"""
    length: float
    width: float
    thickness: float
    label: str = "Board"
    
    def __post_init__(self):
        if self.length <= 0 or self.width <= 0 or self.thickness <= 0:
            raise ValueError("All dimensions must be positive")


@dataclass
class CutPiece:
    """Represents a piece to be cut"""
    length: float
    width: float
    quantity: int
    stock_board_index: int  # Index of the stock board to use
    label: str = ""
    
    def __post_init__(self):
        if self.length <= 0 or self.width <= 0:
            raise ValueError("Dimensions must be positive")
        if self.quantity <= 0:
            raise ValueError("Quantity must be positive")
        if self.stock_board_index < 0:
            raise ValueError("Stock board index must be non-negative")


@dataclass
class PlacedPiece:
    """Represents a piece placed on a board"""
    x: float
    y: float
    width: float
    height: float
    original_width: float
    original_height: float
    rotated: bool
    label: str
    piece_number: int
    total_pieces: int


class Rectangle:
    """Helper class for rectangle packing"""
    def __init__(self, x, y, width, height):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
    
    def area(self):
        return self.width * self.height


class OptimizationEngine:
    """Handles the 2D bin packing optimization"""
    
    def __init__(self, stock_boards: List[StockBoard], cut_pieces: List[CutPiece], 
                 buffer: float, units: str = "in"):
        self.stock_boards = stock_boards
        self.cut_pieces = cut_pieces
        self.buffer = buffer
        self.units = units
        self.results = []
    
    def optimize(self):
        """
        Main optimization method
        Returns list of (stock_board, list of placed_pieces, waste_percentage)
        """
        self.results = []
        
        # Group pieces by stock board index
        pieces_by_board = {}
        for piece in self.cut_pieces:
            if piece.stock_board_index not in pieces_by_board:
                pieces_by_board[piece.stock_board_index] = []
            
            # Expand by quantity
            for i in range(piece.quantity):
                pieces_by_board[piece.stock_board_index].append({
                    'width': piece.length,
                    'height': piece.width,
                    'label': piece.label if piece.label else f"{piece.length}×{piece.width}",
                    'index': i + 1,
                    'total': piece.quantity
                })
        
        # Process each stock board type
        for stock_idx, pieces_to_place in pieces_by_board.items():
            if stock_idx >= len(self.stock_boards):
                continue
                
            stock_board = self.stock_boards[stock_idx]
            
            # Sort by area descending, then by longest dimension
            pieces_to_place.sort(key=lambda p: (p['width'] * p['height'], max(p['width'], p['height'])), reverse=True)
            
            # Pack pieces onto boards of this type
            while pieces_to_place:
                placed, remaining = self._pack_board_maxrect(stock_board, pieces_to_place)
                
                if placed:
                    used_area = sum(p.width * p.height for p in placed)
                    total_area = stock_board.length * stock_board.width
                    waste_pct = ((total_area - used_area) / total_area) * 100
                    
                    self.results.append({
                        'stock_board': stock_board,
                        'placed_pieces': placed,
                        'waste_percentage': waste_pct,
                        'board_number': len(self.results) + 1
                    })
                    
                    pieces_to_place = remaining
                else:
                    # Couldn't place any pieces - this shouldn't happen with proper validation
                    break
        
        return self.results
    
    def _pack_board_maxrect(self, stock_board: StockBoard, pieces: List[dict]):
        """
        Pack pieces using Maximal Rectangles algorithm
        Much better for long thin pieces than guillotine
        """
        placed_pieces = []
        remaining_pieces = pieces.copy()
        
        # Start with the full board as available space
        free_rectangles = [Rectangle(0, 0, stock_board.length, stock_board.width)]
        
        # Keep trying to place pieces
        while remaining_pieces:
            best_piece_idx = None
            best_rect_idx = None
            best_position = None
            best_rotated = False
            best_score = None
            
            # Try to find the best piece-rectangle combination
            for piece_idx, piece in enumerate(remaining_pieces):
                buffer_offset = self.buffer if placed_pieces else 0
                
                for rect_idx, rect in enumerate(free_rectangles):
                    # Try both orientations
                    orientations = [
                        (piece['width'], piece['height'], False),
                        (piece['height'], piece['width'], True)
                    ]
                    
                    for width, height, rotated in orientations:
                        if (width + buffer_offset <= rect.width and 
                            height + buffer_offset <= rect.height):
                            
                            # Score: prefer tighter fit (less wasted space in this rectangle)
                            # Using Best Area Fit: minimize remaining area
                            remaining_area = (rect.width * rect.height) - (width * height)
                            
                            # Also consider aspect ratio match
                            rect_aspect = rect.width / rect.height if rect.height > 0 else 999
                            piece_aspect = width / height if height > 0 else 999
                            aspect_diff = abs(rect_aspect - piece_aspect)
                            
                            # Combined score: primarily area fit, secondarily aspect ratio
                            score = remaining_area + (aspect_diff * 10)
                            
                            if best_score is None or score < best_score:
                                best_score = score
                                best_piece_idx = piece_idx
                                best_rect_idx = rect_idx
                                best_position = (rect.x, rect.y, width, height)
                                best_rotated = rotated
            
            # If we found a placement, place the piece
            if best_piece_idx is not None:
                piece = remaining_pieces[best_piece_idx]
                rect = free_rectangles[best_rect_idx]
                x, y, width, height = best_position
                buffer_offset = self.buffer if placed_pieces else 0
                
                # Create placed piece
                placed_piece = PlacedPiece(
                    x=x + buffer_offset,
                    y=y + buffer_offset,
                    width=width,
                    height=height,
                    original_width=piece['width'],
                    original_height=piece['height'],
                    rotated=best_rotated,
                    label=piece['label'],
                    piece_number=piece['index'],
                    total_pieces=piece['total']
                )
                placed_pieces.append(placed_piece)
                
                # Split the used rectangle and update free rectangles
                self._split_free_rectangle(free_rectangles, best_rect_idx, 
                                          x + buffer_offset, y + buffer_offset, 
                                          width, height, buffer_offset)
                
                # Remove placed piece
                remaining_pieces.pop(best_piece_idx)
            else:
                # Can't place any more pieces
                break
        
        return placed_pieces, remaining_pieces
    
    def _split_free_rectangle(self, free_rects, used_rect_idx, px, py, pw, ph, buffer):
        """
        Split free rectangle after placing a piece
        Uses maximal rectangles approach - generates all maximal free rectangles
        """
        used_rect = free_rects[used_rect_idx]
        new_rects = []
        
        # Generate new free rectangles from the split
        # Right side
        if px + pw + buffer < used_rect.x + used_rect.width:
            new_rects.append(Rectangle(
                px + pw + buffer,
                used_rect.y,
                used_rect.x + used_rect.width - (px + pw + buffer),
                used_rect.height
            ))
        
        # Top side
        if py + ph + buffer < used_rect.y + used_rect.height:
            new_rects.append(Rectangle(
                used_rect.x,
                py + ph + buffer,
                used_rect.width,
                used_rect.y + used_rect.height - (py + ph + buffer)
            ))
        
        # Remove the used rectangle
        free_rects.pop(used_rect_idx)
        
        # Add new rectangles
        for new_rect in new_rects:
            if new_rect.width > 0.01 and new_rect.height > 0.01:  # Only add meaningful rectangles
                # Check if this rectangle is not completely inside another
                is_redundant = False
                for existing in free_rects:
                    if (new_rect.x >= existing.x and 
                        new_rect.y >= existing.y and
                        new_rect.x + new_rect.width <= existing.x + existing.width and
                        new_rect.y + new_rect.height <= existing.y + existing.height):
                        is_redundant = True
                        break
                
                if not is_redundant:
                    free_rects.append(new_rect)
        
        # Remove any rectangles that are now overlapped by the placed piece
        i = 0
        while i < len(free_rects):
            rect = free_rects[i]
            # Check if this rectangle overlaps with the placed piece
            if not (rect.x >= px + pw + buffer or
                    px >= rect.x + rect.width or
                    rect.y >= py + ph + buffer or
                    py >= rect.y + rect.height):
                # There's overlap - we need to split this rectangle
                split_rects = self._split_overlapping_rect(rect, px, py, pw, ph, buffer)
                free_rects.pop(i)
                for sr in split_rects:
                    if sr.width > 0.01 and sr.height > 0.01:
                        free_rects.append(sr)
            else:
                i += 1
        
        # Remove redundant rectangles (ones completely contained in others)
        self._remove_redundant_rectangles(free_rects)
    
    def _split_overlapping_rect(self, rect, px, py, pw, ph, buffer):
        """Split a rectangle that overlaps with a placed piece"""
        splits = []
        piece_right = px + pw + buffer
        piece_top = py + ph + buffer
        
        # Left side
        if rect.x < px:
            splits.append(Rectangle(rect.x, rect.y, px - rect.x, rect.height))
        
        # Right side  
        if rect.x + rect.width > piece_right:
            splits.append(Rectangle(piece_right, rect.y, 
                                  rect.x + rect.width - piece_right, rect.height))
        
        # Bottom side
        if rect.y < py:
            splits.append(Rectangle(rect.x, rect.y, rect.width, py - rect.y))
        
        # Top side
        if rect.y + rect.height > piece_top:
            splits.append(Rectangle(rect.x, piece_top, 
                                  rect.width, rect.y + rect.height - piece_top))
        
        return splits
    
    def _remove_redundant_rectangles(self, rects):
        """Remove rectangles that are completely contained within other rectangles"""
        i = 0
        while i < len(rects):
            j = 0
            is_contained = False
            while j < len(rects):
                if i != j:
                    # Check if rect[i] is completely inside rect[j]
                    if (rects[i].x >= rects[j].x and
                        rects[i].y >= rects[j].y and
                        rects[i].x + rects[i].width <= rects[j].x + rects[j].width and
                        rects[i].y + rects[i].height <= rects[j].y + rects[j].height):
                        is_contained = True
                        break
                j += 1
            
            if is_contained:
                rects.pop(i)
            else:
                i += 1
    
    def validate_pieces(self):
        """Validate that all pieces can fit on their designated stock board"""
        errors = []
        for piece in self.cut_pieces:
            if piece.stock_board_index >= len(self.stock_boards):
                label = piece.label if piece.label else f"{piece.length}×{piece.width}"
                errors.append(f"Piece {label} references invalid stock board")
                continue
                
            stock = self.stock_boards[piece.stock_board_index]
            can_fit = False
            
            # Check if piece fits without rotation
            if piece.length <= stock.length and piece.width <= stock.width:
                can_fit = True
            # Check if piece fits with rotation
            elif piece.width <= stock.length and piece.length <= stock.width:
                can_fit = True
            
            if not can_fit:
                label = piece.label if piece.label else f"{piece.length}×{piece.width}"
                stock_label = stock.label if stock.label else f"Stock board {piece.stock_board_index + 1}"
                errors.append(f"Piece {label} is too large to fit on {stock_label}")
        
        return errors


class PDFGenerator:
    """Generates PDF output with cutting diagrams"""
    
    def __init__(self, results, units, buffer):
        self.results = results
        self.units = units
        self.buffer = buffer
    
    def generate(self, filename):
        """Generate the PDF with cutting diagrams in landscape mode"""
        # Use landscape orientation for better diagram visibility
        from reportlab.lib.pagesizes import landscape
        page_size = landscape(letter)
        c = canvas.Canvas(filename, pagesize=page_size)
        width, height = page_size
        
        # Title page
        c.setFont("Helvetica-Bold", 24)
        c.drawCentredString(width/2, height - 1.5*inch, "Wood Cutting Optimization Report")
        
        c.setFont("Helvetica", 14)
        c.drawCentredString(width/2, height - 2*inch, 
                          f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        c.drawCentredString(width/2, height - 2.4*inch, 
                          f"Units: {self.units} | Buffer: {self.buffer} {self.units}")
        
        # Summary
        y_pos = height - 3.2*inch
        c.setFont("Helvetica-Bold", 16)
        c.drawString(1.5*inch, y_pos, "Summary")
        y_pos -= 0.5*inch
        
        c.setFont("Helvetica", 13)
        c.drawString(1.5*inch, y_pos, f"Total boards required: {len(self.results)}")
        y_pos -= 0.35*inch
        
        total_pieces = sum(len(r['placed_pieces']) for r in self.results)
        c.drawString(1.5*inch, y_pos, f"Total pieces cut: {total_pieces}")
        y_pos -= 0.35*inch
        
        avg_waste = sum(r['waste_percentage'] for r in self.results) / len(self.results)
        c.drawString(1.5*inch, y_pos, f"Average waste: {avg_waste:.1f}%")
        y_pos -= 0.5*inch
        
        # Board-by-board summary
        c.setFont("Helvetica-Bold", 14)
        c.drawString(1.5*inch, y_pos, "Board Breakdown:")
        y_pos -= 0.4*inch
        
        c.setFont("Helvetica", 12)
        for i, result in enumerate(self.results, 1):
            board_summary = f"Board #{i}: {len(result['placed_pieces'])} pieces, {result['waste_percentage']:.1f}% waste"
            c.drawString(2*inch, y_pos, board_summary)
            y_pos -= 0.3*inch
            
            if y_pos < 1.5*inch:
                break
        
        c.showPage()
        
        # Generate diagram for each board
        for result in self.results:
            self._draw_cutting_diagram(c, result)
            c.showPage()
        
        c.save()
    
    def _draw_cutting_diagram(self, c, result):
        """Draw a single cutting diagram - optimized for landscape mode"""
        from reportlab.lib.pagesizes import landscape
        width, height = landscape(letter)
        
        stock_board = result['stock_board']
        placed_pieces = result['placed_pieces']
        board_num = result['board_number']
        
        # Title
        c.setFont("Helvetica-Bold", 18)
        c.drawString(0.75*inch, height - 0.6*inch, 
                    f"Board #{board_num} - {stock_board.label}")
        
        c.setFont("Helvetica", 12)
        c.drawString(0.75*inch, height - 0.9*inch,
                    f"Stock: {stock_board.length} × {stock_board.width} × {stock_board.thickness} {self.units}")
        c.drawString(0.75*inch, height - 1.1*inch,
                    f"Pieces: {len(placed_pieces)} | Waste: {result['waste_percentage']:.1f}%")
        
        # Calculate scaling to use maximum available space
        # Leave room for title (1.3") and cutting list on the right
        margin_left = 0.75 * inch
        margin_top = 1.4 * inch
        margin_bottom = 0.5 * inch
        cutting_list_width = 3.5 * inch  # Space for cutting list on the right
        
        available_width = width - margin_left - cutting_list_width - 0.5*inch
        available_height = height - margin_top - margin_bottom
        
        scale_x = available_width / stock_board.length
        scale_y = available_height / stock_board.width
        scale = min(scale_x, scale_y)  # Use full available space
        
        # Drawing origin (bottom-left of board)
        origin_x = margin_left
        origin_y = margin_bottom
        
        # Draw stock board outline
        board_width_scaled = stock_board.length * scale
        board_height_scaled = stock_board.width * scale
        
        c.setStrokeColor(colors.black)
        c.setLineWidth(3)  # Thicker border for better visibility
        c.rect(origin_x, origin_y, board_width_scaled, board_height_scaled)
        
        # Draw each placed piece with larger labels
        colors_list = [colors.lightblue, colors.lightgreen, colors.lightyellow, 
                      colors.lightcoral, colors.lightgrey, colors.lavender,
                      colors.pink, colors.lightcyan, colors.wheat]
        
        for i, piece in enumerate(placed_pieces):
            x = origin_x + piece.x * scale
            y = origin_y + piece.y * scale
            w = piece.width * scale
            h = piece.height * scale
            
            # Fill rectangle
            c.setFillColor(colors_list[i % len(colors_list)])
            c.setStrokeColor(colors.black)
            c.setLineWidth(1)
            c.rect(x, y, w, h, fill=1, stroke=1)
            
            # Add label with larger, more readable text
            c.setFillColor(colors.black)
            
            # Determine font size based on piece size
            if w > 100 and h > 40:
                font_size = 11
                label_font_size = 10
            elif w > 60 and h > 25:
                font_size = 9
                label_font_size = 8
            else:
                font_size = 8
                label_font_size = 7
            
            label_text = f"{piece.label}"
            if piece.total_pieces > 1:
                label_text += f" (#{piece.piece_number}/{piece.total_pieces})"
            
            dim_text = f"{piece.original_width:.2f}×{piece.original_height:.2f}"
            if piece.rotated:
                dim_text += " ↻"  # Rotation symbol
            
            # Center the text in the rectangle
            text_x = x + w/2
            text_y = y + h/2
            
            c.setFont("Helvetica-Bold", font_size)
            c.drawCentredString(text_x, text_y + 8, label_text)
            c.setFont("Helvetica", label_font_size)
            c.drawCentredString(text_x, text_y - 8, dim_text)
        
        # Add cutting list on the right side
        list_x = origin_x + board_width_scaled + 0.5*inch
        list_y = height - margin_top
        
        c.setFont("Helvetica-Bold", 12)
        c.drawString(list_x, list_y, "Cutting List:")
        list_y -= 0.3*inch
        
        c.setFont("Helvetica", 10)
        for i, piece in enumerate(placed_pieces, 1):
            text = f"{i}. {piece.label}"
            if piece.total_pieces > 1:
                text += f" (#{piece.piece_number}/{piece.total_pieces})"
            
            c.drawString(list_x, list_y, text)
            list_y -= 0.17*inch
            
            dim_text = f"   {piece.original_width:.2f}×{piece.original_height:.2f} {self.units}"
            if piece.rotated:
                dim_text += " [Rotated 90°]"
            
            c.setFont("Helvetica", 9)
            c.drawString(list_x, list_y, dim_text)
            c.setFont("Helvetica", 10)
            list_y -= 0.2*inch
            
            if list_y < 1*inch:  # Don't go off page
                list_y = 1*inch
                c.setFont("Helvetica-Oblique", 9)
                c.drawString(list_x, list_y, "(continued on diagram...)")
                break


class CuttingOptimizerGUI:
    """Main GUI application"""

    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("1100x750")
        self.root.minsize(900, 600)

        # Set application icon (using built-in bitmap)
        try:
            # Try to set a window icon - this creates a simple geometric icon
            self.root.iconbitmap(default='')  # Clear default if any
        except:
            pass  # Ignore if icon setting fails

        # Apply dark mode
        self.setup_dark_mode()

        # Status bar text
        self.status_text = tk.StringVar(value="Ready")

        # Current project data
        self.stock_boards = []
        self.cut_pieces_data = []
        self.units = tk.StringVar(value="in")
        self.buffer = tk.StringVar(value="0.125")

        # Track units change to update labels
        self.units.trace_add('write', lambda *args: self.on_units_changed())

        self.piece_rows = []
        self.stock_board_rows = []

        # Validation state tracking
        self.validation_errors = []

        # Setup keyboard shortcuts
        self.setup_keyboard_shortcuts()

        self.setup_ui()

        # Set initial status
        self.set_status("Ready - Add stock boards and pieces to begin", "ready")
    
    def setup_dark_mode(self):
        """Configure dark mode theme"""
        style = ttk.Style()
        
        # Configure root window
        self.root.configure(bg=DARK_BG)
        
        # Configure ttk styles
        style.theme_use('clam')
        
        # Configure general styles
        style.configure('.', background=DARK_BG, foreground=DARK_FG, 
                       fieldbackground=DARK_INPUT_BG, bordercolor=DARK_BORDER)
        
        # Frame styles
        style.configure('TFrame', background=DARK_BG)
        style.configure('TLabelframe', background=DARK_BG, foreground=DARK_FG,
                       bordercolor=DARK_BORDER)
        style.configure('TLabelframe.Label', background=DARK_BG, foreground=DARK_FG)
        
        # Label styles
        style.configure('TLabel', background=DARK_BG, foreground=DARK_FG)
        
        # Entry styles
        style.configure('TEntry', fieldbackground=DARK_INPUT_BG, foreground=DARK_INPUT_FG,
                       bordercolor=DARK_BORDER, lightcolor=DARK_BORDER, darkcolor=DARK_BORDER,
                       insertcolor=DARK_FG)
        style.map('TEntry', 
                 fieldbackground=[('focus', DARK_SELECT_BG)],
                 lightcolor=[('focus', DARK_ACCENT)])
        
        # Button styles
        style.configure('TButton', background=DARK_BUTTON_BG, foreground=DARK_BUTTON_FG,
                       bordercolor=DARK_BORDER, lightcolor=DARK_BUTTON_BG, darkcolor=DARK_BUTTON_BG)
        style.map('TButton',
                 background=[('active', DARK_SELECT_BG), ('pressed', DARK_SELECT_BG)],
                 foreground=[('active', DARK_FG)])
        
        # Accent button style
        style.configure('Accent.TButton', background=DARK_ACCENT, foreground=DARK_FG)
        style.map('Accent.TButton',
                 background=[('active', '#5eb0ff'), ('pressed', '#3a85cc')])
        
        # Radiobutton styles
        style.configure('TRadiobutton', background=DARK_BG, foreground=DARK_FG,
                       bordercolor=DARK_BORDER)
        style.map('TRadiobutton',
                 background=[('active', DARK_BG)],
                 indicatorcolor=[('selected', DARK_ACCENT)])
        
        # Notebook (tab) styles
        style.configure('TNotebook', background=DARK_BG, bordercolor=DARK_BORDER)
        style.configure('TNotebook.Tab', background=DARK_BUTTON_BG, foreground=DARK_FG,
                       bordercolor=DARK_BORDER, lightcolor=DARK_BORDER)
        style.map('TNotebook.Tab',
                 background=[('selected', DARK_NOTEBOOK_BG), ('active', DARK_SELECT_BG)],
                 foreground=[('selected', DARK_FG)])
        
        # Combobox styles
        style.configure('TCombobox', fieldbackground=DARK_INPUT_BG, background=DARK_BUTTON_BG,
                       foreground=DARK_INPUT_FG, bordercolor=DARK_BORDER,
                       arrowcolor=DARK_FG, selectbackground=DARK_SELECT_BG,
                       selectforeground=DARK_FG)
        style.map('TCombobox',
                 fieldbackground=[('readonly', DARK_INPUT_BG)],
                 selectbackground=[('readonly', DARK_INPUT_BG)],
                 foreground=[('readonly', DARK_INPUT_FG)])
        
        # Scrollbar styles
        style.configure('TScrollbar', background=DARK_BUTTON_BG, bordercolor=DARK_BORDER,
                       arrowcolor=DARK_FG, troughcolor=DARK_BG)
        style.map('TScrollbar',
                 background=[('active', DARK_SELECT_BG)])

        # Panel/Section frame style
        style.configure('Panel.TFrame', background=DARK_PANEL, relief='flat')

        # Header label style
        style.configure('Header.TLabel', background=DARK_BG, foreground=DARK_ACCENT,
                       font=('Arial', 11, 'bold'))

        # Subheader label style
        style.configure('Subheader.TLabel', background=DARK_BG, foreground=DARK_FG,
                       font=('Arial', 9))

        # Status bar style
        style.configure('Status.TLabel', background=DARK_PANEL, foreground=DARK_FG,
                       font=('Arial', 9), padding=(10, 5))

        # Delete button style (subtle danger)
        style.configure('Delete.TButton', background='#4a3030', foreground=DARK_FG)
        style.map('Delete.TButton',
                 background=[('active', '#6b4545'), ('pressed', '#5a3838')])

        # Success button style
        style.configure('Success.TButton', background=DARK_SUCCESS, foreground=DARK_FG)
        style.map('Success.TButton',
                 background=[('active', '#1ed615'), ('pressed', '#13a50d')])

    def setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts for common actions"""
        self.root.bind('<Control-s>', lambda e: self.save_project())
        self.root.bind('<Control-S>', lambda e: self.save_project())
        self.root.bind('<Control-o>', lambda e: self.load_project())
        self.root.bind('<Control-O>', lambda e: self.load_project())
        self.root.bind('<F5>', lambda e: self.run_optimization())
        self.root.bind('<Control-n>', lambda e: self.clear_all())
        self.root.bind('<Control-N>', lambda e: self.clear_all())

    def set_status(self, message, status_type="info"):
        """Update status bar with message and optional color coding"""
        self.status_text.set(message)
        if hasattr(self, 'status_label'):
            if status_type == "error":
                self.status_label.configure(foreground=DARK_ERROR)
            elif status_type == "success":
                self.status_label.configure(foreground=DARK_SUCCESS)
            elif status_type == "warning":
                self.status_label.configure(foreground=DARK_WARNING)
            else:
                self.status_label.configure(foreground=DARK_FG)

    def create_tooltip(self, widget, text):
        """Create a tooltip for a widget"""
        def on_enter(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")

            label = tk.Label(tooltip, text=text, background=DARK_PANEL,
                           foreground=DARK_FG, relief='solid', borderwidth=1,
                           font=('Arial', 9), padx=8, pady=4)
            label.pack()

            widget.tooltip = tooltip

        def on_leave(event):
            if hasattr(widget, 'tooltip'):
                widget.tooltip.destroy()
                del widget.tooltip

        widget.bind('<Enter>', on_enter)
        widget.bind('<Leave>', on_leave)

    def on_units_changed(self):
        """Update unit labels when units are changed"""
        unit = self.units.get()

        # Update buffer unit label
        if hasattr(self, 'buffer_unit_label'):
            self.buffer_unit_label.configure(text=unit)

        # Update stock board header labels
        if hasattr(self, 'stock_header_frame'):
            for widget in self.stock_header_frame.winfo_children():
                text = widget.cget('text')
                if 'Length' in text:
                    widget.configure(text=f"Length ({unit})")
                elif 'Width' in text:
                    widget.configure(text=f"Width ({unit})")
                elif 'Thickness' in text:
                    widget.configure(text=f"Thickness ({unit})")

        # Update pieces header labels
        if hasattr(self, 'pieces_header_frame'):
            for widget in self.pieces_header_frame.winfo_children():
                text = widget.cget('text')
                if 'Length' in text:
                    widget.configure(text=f"Length ({unit})")
                elif 'Width' in text:
                    widget.configure(text=f"Width ({unit})")

    def setup_ui(self):
        """Setup the user interface"""
        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        # Header section with app title
        header_frame = ttk.Frame(main_frame, style='Panel.TFrame')
        header_frame.pack(fill=tk.X, pady=(0, 15))

        title_label = ttk.Label(header_frame, text=f"✂ {APP_NAME}",
                               font=('Arial', 16, 'bold'), foreground=DARK_ACCENT,
                               background=DARK_PANEL)
        title_label.pack(side=tk.LEFT, padx=10, pady=10)

        version_label = ttk.Label(header_frame, text=f"v{APP_VERSION}",
                                 font=('Arial', 9), foreground=DARK_INPUT_FG,
                                 background=DARK_PANEL)
        version_label.pack(side=tk.LEFT, pady=10)

        # Top controls panel
        top_panel = ttk.Frame(main_frame, style='Panel.TFrame')
        top_panel.pack(fill=tk.X, pady=(0, 12))

        # Left side - Units and buffer
        left_controls = ttk.Frame(top_panel, style='Panel.TFrame')
        left_controls.pack(side=tk.LEFT, padx=10, pady=10)

        # Unit toggle with modern styling
        units_label = ttk.Label(left_controls, text="Units:", style='Header.TLabel')
        units_label.grid(row=0, column=0, padx=(0, 10), sticky='w')
        self.create_tooltip(units_label, "Select measurement units for all dimensions")

        ttk.Radiobutton(left_controls, text="Inches (in)", variable=self.units,
                       value="in").grid(row=0, column=1, padx=5)
        ttk.Radiobutton(left_controls, text="Centimeters (cm)", variable=self.units,
                       value="cm").grid(row=0, column=2, padx=5)

        # Buffer input with unit label
        buffer_label = ttk.Label(left_controls, text="Saw Kerf:", style='Header.TLabel')
        buffer_label.grid(row=1, column=0, padx=(0, 10), pady=(10, 0), sticky='w')
        self.create_tooltip(buffer_label, "Blade width/cutting buffer to account for material loss")

        buffer_entry = ttk.Entry(left_controls, textvariable=self.buffer, width=10)
        buffer_entry.grid(row=1, column=1, padx=5, pady=(10, 0), sticky='w')

        self.buffer_unit_label = ttk.Label(left_controls, text=self.units.get(),
                                          foreground=DARK_INPUT_FG, background=DARK_PANEL)
        self.buffer_unit_label.grid(row=1, column=2, padx=(0, 5), pady=(10, 0), sticky='w')

        # Right side - File operations
        right_controls = ttk.Frame(top_panel, style='Panel.TFrame')
        right_controls.pack(side=tk.RIGHT, padx=10, pady=10)

        save_btn = ttk.Button(right_controls, text="💾 Save Project (Ctrl+S)",
                             command=self.save_project)
        save_btn.grid(row=0, column=0, padx=5)
        self.create_tooltip(save_btn, "Save current project to JSON file")

        load_btn = ttk.Button(right_controls, text="📂 Load Project (Ctrl+O)",
                             command=self.load_project)
        load_btn.grid(row=0, column=1, padx=5)
        self.create_tooltip(load_btn, "Load project from JSON file")

        # Create notebook for tabs with better styling
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 12))

        # Stock Boards Tab
        stock_frame = ttk.Frame(notebook)
        notebook.add(stock_frame, text="📐 Stock Boards")
        self.setup_stock_board_tab(stock_frame)

        # Cut Pieces Tab
        pieces_frame = ttk.Frame(notebook)
        notebook.add(pieces_frame, text="✂ Pieces to Cut")
        self.setup_cut_pieces_tab(pieces_frame)

        # Bottom action buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))

        optimize_btn = ttk.Button(button_frame, text="🚀 Calculate Optimization (F5)",
                                 command=self.run_optimization,
                                 style='Success.TButton')
        optimize_btn.pack(side=tk.LEFT, padx=5, ipadx=20, ipady=5)
        self.create_tooltip(optimize_btn, "Run optimization algorithm to generate cutting plan")

        ttk.Button(button_frame, text="🗑 Clear All (Ctrl+N)",
                  command=self.clear_all,
                  style='Delete.TButton').pack(side=tk.LEFT, padx=5)

        # Keyboard shortcuts hint
        shortcuts_label = ttk.Label(button_frame,
                                   text="Shortcuts: Ctrl+S=Save | Ctrl+O=Load | F5=Optimize | Ctrl+N=Clear",
                                   font=('Arial', 8), foreground=DARK_INPUT_FG)
        shortcuts_label.pack(side=tk.RIGHT, padx=10)

        # Status bar at the bottom
        status_frame = ttk.Frame(self.root, style='Panel.TFrame', relief='sunken')
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.status_label = ttk.Label(status_frame, textvariable=self.status_text,
                                     style='Status.TLabel', anchor='w')
        self.status_label.pack(fill=tk.X, side=tk.LEFT)
    
    def setup_stock_board_tab(self, parent):
        """Setup the stock boards input tab"""
        # Instructions with modern styling
        inst_frame = ttk.Frame(parent, style='Panel.TFrame')
        inst_frame.pack(fill=tk.X, padx=12, pady=12)

        ttk.Label(inst_frame, text="📐 Define Your Stock Board Sizes",
                 style='Header.TLabel').pack(anchor=tk.W, padx=8, pady=(8, 2))
        ttk.Label(inst_frame, text="Enter the dimensions of uncut boards you have available",
                 style='Subheader.TLabel').pack(anchor=tk.W, padx=8, pady=(0, 8))
        
        # Container for scrollable area and button
        container = ttk.Frame(parent)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Scrollable frame for stock boards
        canvas = tk.Canvas(container, bg=DARK_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.stock_scrollable_frame = ttk.Frame(canvas)
        
        self.stock_scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.stock_scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Header row with unit indicators
        header_frame = ttk.Frame(self.stock_scrollable_frame, style='Panel.TFrame')
        header_frame.pack(fill=tk.X, pady=8, padx=5)

        ttk.Label(header_frame, text="Label", font=('Arial', 9, 'bold'),
                 width=15).grid(row=0, column=0, padx=5, sticky='w')
        ttk.Label(header_frame, text=f"Length ({self.units.get()})",
                 font=('Arial', 9, 'bold'), width=12).grid(row=0, column=1, padx=5, sticky='w')
        ttk.Label(header_frame, text=f"Width ({self.units.get()})",
                 font=('Arial', 9, 'bold'), width=12).grid(row=0, column=2, padx=5, sticky='w')
        ttk.Label(header_frame, text=f"Thickness ({self.units.get()})",
                 font=('Arial', 9, 'bold'), width=14).grid(row=0, column=3, padx=5, sticky='w')
        ttk.Label(header_frame, text="", width=8).grid(row=0, column=4)

        # Store header frame to update units later
        self.stock_header_frame = header_frame
        
        # Add initial stock board row
        self.add_stock_board_row()
        
        # Add button pinned to bottom with modern styling
        add_btn_frame = ttk.Frame(parent, style='Panel.TFrame')
        add_btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=12, padx=12)
        add_btn = ttk.Button(add_btn_frame, text="➕ Add Stock Board",
                            command=self.add_stock_board_row, style='Accent.TButton')
        add_btn.pack(ipadx=10, ipady=3)
        self.create_tooltip(add_btn, "Add another stock board size")
    
    def setup_cut_pieces_tab(self, parent):
        """Setup the cut pieces input tab"""
        # Instructions with modern styling
        inst_frame = ttk.Frame(parent, style='Panel.TFrame')
        inst_frame.pack(fill=tk.X, padx=12, pady=12)

        ttk.Label(inst_frame, text="✂ Define Pieces to Cut",
                 style='Header.TLabel').pack(anchor=tk.W, padx=8, pady=(8, 2))
        ttk.Label(inst_frame, text="Enter dimensions, quantities, and select the stock board for each piece",
                 style='Subheader.TLabel').pack(anchor=tk.W, padx=8, pady=(0, 8))
        
        # Container for scrollable area and button
        container = ttk.Frame(parent)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Scrollable frame for cut pieces
        canvas = tk.Canvas(container, bg=DARK_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.pieces_scrollable_frame = ttk.Frame(canvas)
        
        self.pieces_scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.pieces_scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Header row with unit indicators
        header_frame = ttk.Frame(self.pieces_scrollable_frame, style='Panel.TFrame')
        header_frame.pack(fill=tk.X, pady=8, padx=5)

        ttk.Label(header_frame, text="Label (Optional)", font=('Arial', 9, 'bold'),
                 width=15).grid(row=0, column=0, padx=5, sticky='w')
        ttk.Label(header_frame, text=f"Length ({self.units.get()})",
                 font=('Arial', 9, 'bold'), width=12).grid(row=0, column=1, padx=5, sticky='w')
        ttk.Label(header_frame, text=f"Width ({self.units.get()})",
                 font=('Arial', 9, 'bold'), width=12).grid(row=0, column=2, padx=5, sticky='w')
        ttk.Label(header_frame, text="Quantity", font=('Arial', 9, 'bold'),
                 width=10).grid(row=0, column=3, padx=5, sticky='w')
        ttk.Label(header_frame, text="Stock Board", font=('Arial', 9, 'bold'),
                 width=20).grid(row=0, column=4, padx=5, sticky='w')
        ttk.Label(header_frame, text="", width=8).grid(row=0, column=5)

        # Store header frame to update units later
        self.pieces_header_frame = header_frame
        
        # Add initial row
        self.add_piece_row()
        
        # Add button pinned to bottom with modern styling
        add_btn_frame = ttk.Frame(parent, style='Panel.TFrame')
        add_btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=12, padx=12)
        add_btn = ttk.Button(add_btn_frame, text="➕ Add Piece",
                            command=self.add_piece_row, style='Accent.TButton')
        add_btn.pack(ipadx=10, ipady=3)
        self.create_tooltip(add_btn, "Add another piece to cut")
    
    def add_stock_board_row(self):
        """Add a new stock board input row"""
        row_frame = ttk.Frame(self.stock_scrollable_frame)
        row_frame.pack(fill=tk.X, pady=2)
        
        label_var = tk.StringVar(value=f"Board {len(self.stock_board_rows) + 1}")
        length_var = tk.StringVar()
        width_var = tk.StringVar()
        thickness_var = tk.StringVar()
        
        ttk.Entry(row_frame, textvariable=label_var, width=15).grid(row=0, column=0, padx=5)
        ttk.Entry(row_frame, textvariable=length_var, width=10).grid(row=0, column=1, padx=5)
        ttk.Entry(row_frame, textvariable=width_var, width=10).grid(row=0, column=2, padx=5)
        thickness_entry = ttk.Entry(row_frame, textvariable=thickness_var, width=10)
        thickness_entry.grid(row=0, column=3, padx=5)
        
        # Bind thickness change to update piece dropdowns
        thickness_var.trace_add('write', lambda *args: self.update_all_stock_board_dropdowns())
        label_var.trace_add('write', lambda *args: self.update_all_stock_board_dropdowns())
        
        remove_btn = ttk.Button(row_frame, text="✖",
                               command=lambda: self.remove_stock_board_row(row_frame),
                               style='Delete.TButton', width=3)
        remove_btn.grid(row=0, column=4, padx=5)
        self.create_tooltip(remove_btn, "Remove this stock board")
        
        self.stock_board_rows.append({
            'frame': row_frame,
            'label': label_var,
            'length': length_var,
            'width': width_var,
            'thickness': thickness_var
        })
        
        # Update piece dropdowns
        self.update_all_stock_board_dropdowns()
    
    def get_stock_board_options(self):
        """Get list of stock board options for dropdown"""
        options = []
        for i, row in enumerate(self.stock_board_rows):
            label = row['label'].get().strip()
            thickness = row['thickness'].get().strip()
            
            if not label:
                label = f"Board {i + 1}"
            
            if thickness:
                option = f"{label} ({thickness})"
            else:
                option = f"{label} (no thickness)"
            
            options.append(option)
        
        return options if options else ["No stock boards defined"]
    
    def update_all_stock_board_dropdowns(self):
        """Update all stock board dropdowns in piece rows"""
        options = self.get_stock_board_options()
        
        for piece_row in self.piece_rows:
            combobox = piece_row['stock_board_combo']
            current_value = combobox.get()
            combobox['values'] = options
            
            # Try to keep the same selection if still valid
            if current_value in options:
                combobox.set(current_value)
            elif options and options[0] != "No stock boards defined":
                combobox.current(0)
    
    def add_piece_row(self):
        """Add a new cut piece input row"""
        row_frame = ttk.Frame(self.pieces_scrollable_frame)
        row_frame.pack(fill=tk.X, pady=2)
        
        label_var = tk.StringVar()
        length_var = tk.StringVar()
        width_var = tk.StringVar()
        quantity_var = tk.StringVar(value="1")
        
        ttk.Entry(row_frame, textvariable=label_var, width=15).grid(row=0, column=0, padx=5)
        ttk.Entry(row_frame, textvariable=length_var, width=10).grid(row=0, column=1, padx=5)
        ttk.Entry(row_frame, textvariable=width_var, width=10).grid(row=0, column=2, padx=5)
        ttk.Entry(row_frame, textvariable=quantity_var, width=10).grid(row=0, column=3, padx=5)
        
        # Stock board selection dropdown
        stock_board_combo = ttk.Combobox(row_frame, state='readonly', width=18)
        stock_board_combo.grid(row=0, column=4, padx=5)
        stock_board_combo['values'] = self.get_stock_board_options()
        if stock_board_combo['values'] and stock_board_combo['values'][0] != "No stock boards defined":
            stock_board_combo.current(0)
        
        remove_btn = ttk.Button(row_frame, text="✖",
                               command=lambda: self.remove_piece_row(row_frame),
                               style='Delete.TButton', width=3)
        remove_btn.grid(row=0, column=5, padx=5)
        self.create_tooltip(remove_btn, "Remove this piece")
        
        self.piece_rows.append({
            'frame': row_frame,
            'label': label_var,
            'length': length_var,
            'width': width_var,
            'quantity': quantity_var,
            'stock_board_combo': stock_board_combo
        })
    
    def remove_stock_board_row(self, frame):
        """Remove a stock board row"""
        for row in self.stock_board_rows:
            if row['frame'] == frame:
                self.stock_board_rows.remove(row)
                frame.destroy()
                break
        
        # Update all piece dropdowns
        self.update_all_stock_board_dropdowns()
    
    def remove_piece_row(self, frame):
        """Remove a piece row"""
        for row in self.piece_rows:
            if row['frame'] == frame:
                self.piece_rows.remove(row)
                frame.destroy()
                break
    
    def validate_inputs(self):
        """Validate all inputs"""
        errors = []
        
        # Validate buffer
        try:
            buffer_val = float(self.buffer.get())
            if buffer_val < 0:
                errors.append("Buffer must be non-negative")
            if buffer_val > 10:
                errors.append("Warning: Buffer distance seems unusually large (>10)")
        except ValueError:
            errors.append("Buffer must be a valid number")
        
        # Validate stock boards
        stock_boards = []
        for i, row in enumerate(self.stock_board_rows, 1):
            try:
                label = row['label'].get().strip()
                length = float(row['length'].get())
                width = float(row['width'].get())
                thickness = float(row['thickness'].get())
                
                if length <= 0 or width <= 0 or thickness <= 0:
                    errors.append(f"Stock board {i}: All dimensions must be positive")
                else:
                    stock_boards.append(StockBoard(length, width, thickness, label))
            except ValueError:
                errors.append(f"Stock board {i}: Invalid dimensions (must be numbers)")
        
        if not stock_boards:
            errors.append("At least one stock board must be defined")
        
        # Validate cut pieces
        cut_pieces = []
        for i, row in enumerate(self.piece_rows, 1):
            try:
                label = row['label'].get().strip()
                length = float(row['length'].get())
                width = float(row['width'].get())
                quantity = int(row['quantity'].get())
                
                # Get stock board index from combobox
                stock_board_selection = row['stock_board_combo'].get()
                if stock_board_selection == "No stock boards defined" or not stock_board_selection:
                    errors.append(f"Piece {i}: Must select a stock board")
                    continue
                
                # Find the index of the selected stock board
                stock_board_options = self.get_stock_board_options()
                try:
                    stock_board_index = stock_board_options.index(stock_board_selection)
                except ValueError:
                    errors.append(f"Piece {i}: Invalid stock board selection")
                    continue
                
                if length <= 0 or width <= 0:
                    errors.append(f"Piece {i}: Dimensions must be positive")
                elif quantity <= 0:
                    errors.append(f"Piece {i}: Quantity must be positive")
                else:
                    cut_pieces.append(CutPiece(length, width, quantity, stock_board_index, label))
            except ValueError:
                errors.append(f"Piece {i}: Invalid values")
        
        if not cut_pieces:
            errors.append("At least one piece to cut must be defined")
        
        return errors, stock_boards, cut_pieces
    
    def run_optimization(self):
        """Run the optimization and generate outputs"""
        self.set_status("Validating inputs...", "info")

        # Validate inputs
        errors, stock_boards, cut_pieces = self.validate_inputs()

        if errors:
            self.set_status(f"Validation failed: {len(errors)} error(s) found", "error")
            messagebox.showerror("Validation Error", "\n".join(errors))
            return
        
        # Additional validation - check if pieces can fit
        try:
            self.set_status("Checking piece sizes...", "info")
            buffer_val = float(self.buffer.get())
            engine = OptimizationEngine(stock_boards, cut_pieces, buffer_val, self.units.get())
            fit_errors = engine.validate_pieces()

            if fit_errors:
                self.set_status("Validation failed: Pieces too large", "error")
                messagebox.showerror("Piece Too Large", "\n".join(fit_errors))
                return
        except Exception as e:
            self.set_status(f"Validation error: {str(e)}", "error")
            messagebox.showerror("Error", f"Validation failed: {str(e)}")
            return

        # Run optimization
        try:
            self.set_status("Running optimization algorithm...", "info")
            results = engine.optimize()

            if not results:
                self.set_status("Optimization failed", "error")
                messagebox.showerror("Error", "Could not optimize cutting layout")
                return

            # Show results summary
            total_boards = len(results)
            total_pieces = sum(len(r['placed_pieces']) for r in results)
            avg_waste = sum(r['waste_percentage'] for r in results) / len(results)

            self.set_status(f"✓ Optimization complete: {total_boards} boards, {avg_waste:.1f}% avg waste", "success")

            summary = f"Optimization Complete!\n\n"
            summary += f"Total boards needed: {total_boards}\n"
            summary += f"Total pieces cut: {total_pieces}\n"
            summary += f"Average waste: {avg_waste:.1f}%\n\n"
            summary += "Would you like to export the results?"

            if messagebox.askyesno("Optimization Complete", summary):
                self.export_results(results)
            else:
                self.set_status("Optimization complete - Results not exported", "info")

        except Exception as e:
            self.set_status(f"Optimization error: {str(e)}", "error")
            messagebox.showerror("Optimization Error", f"An error occurred: {str(e)}")
    
    def export_results(self, results):
        """Export results to PDF and text file"""
        # Ask for save location
        filename = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            title="Save Cutting Diagrams"
        )

        if not filename:
            self.set_status("Export cancelled", "info")
            return

        try:
            self.set_status("Generating PDF...", "info")
            # Generate PDF
            buffer_val = float(self.buffer.get())
            pdf_gen = PDFGenerator(results, self.units.get(), buffer_val)
            pdf_gen.generate(filename)

            self.set_status("Generating cutting list...", "info")
            # Generate text file
            txt_filename = filename.rsplit('.', 1)[0] + "_cutting_list.txt"
            self.generate_text_report(results, txt_filename)

            self.set_status(f"✓ Files exported successfully", "success")
            messagebox.showinfo("Export Complete",
                              f"Files saved:\n{filename}\n{txt_filename}")

        except Exception as e:
            self.set_status(f"Export failed: {str(e)}", "error")
            messagebox.showerror("Export Error", f"Failed to export: {str(e)}")
    
    def generate_text_report(self, results, filename):
        """Generate a text cutting list"""
        with open(filename, 'w') as f:
            f.write("WOOD CUTTING OPTIMIZATION REPORT\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Units: {self.units.get()}\n")
            f.write(f"Buffer/Kerf: {self.buffer.get()} {self.units.get()}\n\n")
            
            f.write("SUMMARY\n")
            f.write("-" * 60 + "\n")
            f.write(f"Total boards required: {len(results)}\n")
            total_pieces = sum(len(r['placed_pieces']) for r in results)
            f.write(f"Total pieces cut: {total_pieces}\n")
            avg_waste = sum(r['waste_percentage'] for r in results) / len(results)
            f.write(f"Average waste: {avg_waste:.1f}%\n\n")
            
            for result in results:
                board_num = result['board_number']
                stock = result['stock_board']
                pieces = result['placed_pieces']
                
                f.write(f"\nBOARD #{board_num} - {stock.label}\n")
                f.write("-" * 60 + "\n")
                f.write(f"Stock dimensions: {stock.length} × {stock.width} × {stock.thickness} {self.units.get()}\n")
                f.write(f"Pieces to cut: {len(pieces)}\n")
                f.write(f"Waste: {result['waste_percentage']:.1f}%\n\n")
                
                f.write("Cutting List:\n")
                for i, piece in enumerate(pieces, 1):
                    label = piece.label
                    if piece.total_pieces > 1:
                        label += f" (#{piece.piece_number}/{piece.total_pieces})"
                    
                    f.write(f"  {i}. {label}\n")
                    f.write(f"     Dimensions: {piece.original_width:.2f} × {piece.original_height:.2f} {self.units.get()}\n")
                    if piece.rotated:
                        f.write(f"     Note: ROTATED 90°\n")
                    f.write(f"     Position: X={piece.x:.2f}, Y={piece.y:.2f}\n\n")
    
    def save_project(self):
        """Save current project to JSON file"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Save Project"
        )

        if not filename:
            self.set_status("Save cancelled", "info")
            return

        try:
            self.set_status("Saving project...", "info")

            # Collect all data
            stock_boards = []
            for row in self.stock_board_rows:
                if row['length'].get() and row['width'].get() and row['thickness'].get():
                    stock_boards.append({
                        'label': row['label'].get(),
                        'length': row['length'].get(),
                        'width': row['width'].get(),
                        'thickness': row['thickness'].get()
                    })

            cut_pieces = []
            stock_board_options = self.get_stock_board_options()
            for row in self.piece_rows:
                if row['length'].get() and row['width'].get():
                    stock_board_selection = row['stock_board_combo'].get()
                    stock_board_index = -1
                    if stock_board_selection and stock_board_selection != "No stock boards defined":
                        try:
                            stock_board_index = stock_board_options.index(stock_board_selection)
                        except ValueError:
                            stock_board_index = -1

                    cut_pieces.append({
                        'label': row['label'].get(),
                        'length': row['length'].get(),
                        'width': row['width'].get(),
                        'quantity': row['quantity'].get(),
                        'stock_board_index': stock_board_index
                    })

            project_data = {
                'units': self.units.get(),
                'buffer': self.buffer.get(),
                'stock_boards': stock_boards,
                'cut_pieces': cut_pieces
            }

            with open(filename, 'w') as f:
                json.dump(project_data, f, indent=2)

            self.set_status(f"✓ Project saved successfully", "success")
            messagebox.showinfo("Success", "Project saved successfully")

        except Exception as e:
            self.set_status(f"Save failed: {str(e)}", "error")
            messagebox.showerror("Save Error", f"Failed to save project: {str(e)}")
    
    def load_project(self):
        """Load project from JSON file"""
        filename = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Load Project"
        )

        if not filename:
            self.set_status("Load cancelled", "info")
            return

        try:
            self.set_status("Loading project...", "info")

            with open(filename, 'r') as f:
                project_data = json.load(f)

            # Clear existing data WITHOUT adding default rows
            self._clear_all_silent()

            # Load settings
            self.units.set(project_data.get('units', 'in'))
            self.buffer.set(project_data.get('buffer', '0.125'))

            # Load stock boards FIRST (so indices are correct)
            stock_boards_data = project_data.get('stock_boards', [])
            if not stock_boards_data:
                # If no stock boards in file, add one default
                self.add_stock_board_row()
            else:
                for board_data in stock_boards_data:
                    self.add_stock_board_row()
                    row = self.stock_board_rows[-1]
                    row['label'].set(board_data.get('label', ''))
                    row['length'].set(board_data.get('length', ''))
                    row['width'].set(board_data.get('width', ''))
                    row['thickness'].set(board_data.get('thickness', ''))

            # Update dropdowns after loading stock boards
            self.update_all_stock_board_dropdowns()
            stock_board_options = self.get_stock_board_options()

            # Load cut pieces AFTER stock boards are loaded
            cut_pieces_data = project_data.get('cut_pieces', [])
            if not cut_pieces_data:
                # If no pieces in file, add one default
                self.add_piece_row()
            else:
                for piece_data in cut_pieces_data:
                    self.add_piece_row()
                    row = self.piece_rows[-1]
                    row['label'].set(piece_data.get('label', ''))
                    row['length'].set(piece_data.get('length', ''))
                    row['width'].set(piece_data.get('width', ''))
                    row['quantity'].set(piece_data.get('quantity', '1'))

                    # Set stock board selection using the saved index
                    stock_board_index = piece_data.get('stock_board_index', 0)
                    if 0 <= stock_board_index < len(stock_board_options):
                        if stock_board_options[stock_board_index] != "No stock boards defined":
                            row['stock_board_combo'].current(stock_board_index)
                    else:
                        # Index out of range, default to first board if available
                        if stock_board_options and stock_board_options[0] != "No stock boards defined":
                            row['stock_board_combo'].current(0)

            self.set_status(f"✓ Project loaded successfully", "success")
            messagebox.showinfo("Success", "Project loaded successfully")

        except Exception as e:
            self.set_status(f"Load failed: {str(e)}", "error")
            messagebox.showerror("Load Error", f"Failed to load project: {str(e)}")
    
    def _clear_all_silent(self):
        """Clear all inputs without confirmation (used for loading)"""
        # Clear stock board rows
        for row in self.stock_board_rows[:]:
            row['frame'].destroy()
        self.stock_board_rows.clear()
        
        # Clear piece rows
        for row in self.piece_rows[:]:
            row['frame'].destroy()
        self.piece_rows.clear()
        
        # Reset defaults
        self.units.set("in")
        self.buffer.set("0.125")
    
    def clear_all(self):
        """Clear all inputs"""
        if messagebox.askyesno("Clear All", "Are you sure you want to clear all inputs?"):
            self._clear_all_silent()
            # Add default rows after clearing
            self.add_stock_board_row()
            self.add_piece_row()
            self.set_status("All inputs cleared", "info")
        else:
            self.set_status("Clear cancelled", "info")


def main():
    """Main entry point"""
    root = tk.Tk()
    app = CuttingOptimizerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
