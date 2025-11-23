#!/usr/bin/env python3
"""
Wood Cut Optimizer - Mobile Companion App
Lightweight Flask web app for mobile access
"""

from flask import Flask, render_template, request, jsonify, send_file
from dataclasses import dataclass, asdict
from typing import List, Dict
import json
import io
from datetime import datetime

# Reuse core classes from desktop app
@dataclass
class StockBoard:
    """Represents an uncut stock board"""
    length: float
    width: float
    thickness: float
    label: str = "Board"

@dataclass
class CutPiece:
    """Represents a piece to be cut"""
    length: float
    width: float
    quantity: int
    stock_board_index: int
    label: str = ""

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
        """Main optimization method"""
        self.results = []

        # Group pieces by stock board index
        pieces_by_board = {}
        for piece in self.cut_pieces:
            if piece.stock_board_index not in pieces_by_board:
                pieces_by_board[piece.stock_board_index] = []

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
            pieces_to_place.sort(key=lambda p: (p['width'] * p['height'], max(p['width'], p['height'])), reverse=True)

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
                    break

        return self.results

    def _pack_board_maxrect(self, stock_board: StockBoard, pieces: List[dict]):
        """Pack pieces using Maximal Rectangles algorithm"""
        placed_pieces = []
        remaining_pieces = pieces.copy()
        free_rectangles = [Rectangle(0, 0, stock_board.length, stock_board.width)]

        while remaining_pieces:
            best_piece_idx = None
            best_rect_idx = None
            best_position = None
            best_rotated = False
            best_score = None

            for piece_idx, piece in enumerate(remaining_pieces):
                buffer_offset = self.buffer if placed_pieces else 0

                for rect_idx, rect in enumerate(free_rectangles):
                    orientations = [
                        (piece['width'], piece['height'], False),
                        (piece['height'], piece['width'], True)
                    ]

                    for width, height, rotated in orientations:
                        if (width + buffer_offset <= rect.width and
                            height + buffer_offset <= rect.height):

                            remaining_area = (rect.width * rect.height) - (width * height)
                            rect_aspect = rect.width / rect.height if rect.height > 0 else 999
                            piece_aspect = width / height if height > 0 else 999
                            aspect_diff = abs(rect_aspect - piece_aspect)
                            score = remaining_area + (aspect_diff * 10)

                            if best_score is None or score < best_score:
                                best_score = score
                                best_piece_idx = piece_idx
                                best_rect_idx = rect_idx
                                best_position = (rect.x, rect.y, width, height)
                                best_rotated = rotated

            if best_piece_idx is not None:
                piece = remaining_pieces[best_piece_idx]
                rect = free_rectangles[best_rect_idx]
                x, y, width, height = best_position
                buffer_offset = self.buffer if placed_pieces else 0

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

                self._split_free_rectangle(free_rectangles, best_rect_idx,
                                          x + buffer_offset, y + buffer_offset,
                                          width, height, buffer_offset)

                remaining_pieces.pop(best_piece_idx)
            else:
                break

        return placed_pieces, remaining_pieces

    def _split_free_rectangle(self, free_rects, used_rect_idx, px, py, pw, ph, buffer):
        """Split free rectangle after placing a piece"""
        used_rect = free_rects[used_rect_idx]
        new_rects = []

        if px + pw + buffer < used_rect.x + used_rect.width:
            new_rects.append(Rectangle(
                px + pw + buffer,
                used_rect.y,
                used_rect.x + used_rect.width - (px + pw + buffer),
                used_rect.height
            ))

        if py + ph + buffer < used_rect.y + used_rect.height:
            new_rects.append(Rectangle(
                used_rect.x,
                py + ph + buffer,
                used_rect.width,
                used_rect.y + used_rect.height - (py + ph + buffer)
            ))

        free_rects.pop(used_rect_idx)

        for new_rect in new_rects:
            if new_rect.width > 0.01 and new_rect.height > 0.01:
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


# Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'wood-cut-optimizer-mobile'


@app.route('/')
def index():
    """Main page"""
    return render_template('mobile_index.html')


@app.route('/api/optimize', methods=['POST'])
def optimize():
    """Run optimization"""
    try:
        data = request.json

        # Parse stock boards
        stock_boards = [
            StockBoard(
                length=float(b['length']),
                width=float(b['width']),
                thickness=float(b['thickness']),
                label=b.get('label', 'Board')
            )
            for b in data['stock_boards']
        ]

        # Parse cut pieces
        cut_pieces = [
            CutPiece(
                length=float(p['length']),
                width=float(p['width']),
                quantity=int(p['quantity']),
                stock_board_index=int(p['stock_board_index']),
                label=p.get('label', '')
            )
            for p in data['cut_pieces']
        ]

        buffer = float(data.get('buffer', 0.125))
        units = data.get('units', 'in')

        # Run optimization
        engine = OptimizationEngine(stock_boards, cut_pieces, buffer, units)
        results = engine.optimize()

        # Calculate shopping list
        shopping_list = calculate_shopping_list(results)

        # Format results for JSON
        formatted_results = []
        for result in results:
            formatted_results.append({
                'board_number': result['board_number'],
                'stock_board': {
                    'label': result['stock_board'].label,
                    'length': result['stock_board'].length,
                    'width': result['stock_board'].width,
                    'thickness': result['stock_board'].thickness
                },
                'waste_percentage': round(result['waste_percentage'], 1),
                'pieces_count': len(result['placed_pieces']),
                'placed_pieces': [
                    {
                        'x': p.x,
                        'y': p.y,
                        'width': p.width,
                        'height': p.height,
                        'original_width': p.original_width,
                        'original_height': p.original_height,
                        'rotated': p.rotated,
                        'label': p.label,
                        'piece_number': p.piece_number,
                        'total_pieces': p.total_pieces
                    }
                    for p in result['placed_pieces']
                ]
            })

        return jsonify({
            'success': True,
            'results': formatted_results,
            'shopping_list': shopping_list,
            'summary': {
                'total_boards': len(results),
                'total_pieces': sum(len(r['placed_pieces']) for r in results),
                'avg_waste': round(sum(r['waste_percentage'] for r in results) / len(results), 1) if results else 0
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


def calculate_shopping_list(results):
    """Calculate shopping list of stock boards needed"""
    shopping_list = {}

    for result in results:
        stock_board = result['stock_board']
        key = f"{stock_board.label}|{stock_board.length}|{stock_board.width}|{stock_board.thickness}"

        if key not in shopping_list:
            shopping_list[key] = {
                'label': stock_board.label,
                'length': stock_board.length,
                'width': stock_board.width,
                'thickness': stock_board.thickness,
                'quantity': 0
            }

        shopping_list[key]['quantity'] += 1

    return list(shopping_list.values())


if __name__ == '__main__':
    # Run on all network interfaces so it's accessible from mobile devices
    app.run(host='0.0.0.0', port=5000, debug=True)
