"""
Design System for the Video Forensic Analyzer
Provides consistent styling, colors, fonts, and spacing across the application.
"""

from PyQt6.QtGui import QColor, QFont, QFontDatabase
from PyQt6.QtWidgets import QApplication

# Color Palette
COLORS = {
    # Primary Colors
    'primary': QColor(30, 144, 255),      # DodgerBlue
    'primary_dark': QColor(25, 118, 210), # Darker blue
    'primary_light': QColor(70, 180, 255), # Lighter blue
    
    # Secondary Colors
    'secondary': QColor(46, 125, 50),     # Green (success)
    'secondary_dark': QColor(38, 93, 40), # Darker green 
    'secondary_light': QColor(76, 175, 80), # Lighter green
    
    # Warning/Alert Colors
    'warning': QColor(255, 152, 0),       # Orange
    'warning_dark': QColor(255, 111, 0),  # Darker orange
    'warning_light': QColor(255, 204, 128), # Lighter orange
    
    # Error/Reject Colors
    'error': QColor(244, 67, 54),         # Red
    'error_dark': QColor(211, 47, 47),    # Darker red
    'error_light': QColor(255, 138, 128), # Lighter red
    
    # Neutral Colors
    'background': QColor(245, 245, 245),  # Light gray background  
    'surface': QColor(255, 255, 255),     # White surface
    'surface_dark': QColor(240, 240, 240), # Slightly darker surface
    
    'text_primary': QColor(33, 33, 33),   # Dark text
    'text_secondary': QColor(117, 117, 117), # Medium gray text
    'text_disabled': QColor(189, 189, 189), # Disabled text
    
    'border': QColor(224, 224, 224),      # Light border
    'divider': QColor(238, 238, 238),     # Divider line
    
    # Status Colors  
    'status_success': QColor(76, 175, 80),   # Green for success
    'status_warning': QColor(255, 152, 0),   # Orange for warning
    'status_error': QColor(244, 67, 54),     # Red for error
    'status_info': QColor(30, 144, 255),     # Blue for info
    
    # Analysis Colors (for different analysis results)
    'analysis_unaffected': QColor(76, 175, 80),   # Green - unaffected / normal
    'analysis_affected': QColor(255, 152, 0),     # Orange - affected / questionable 
    'analysis_suspicious': QColor(244, 67, 54),   # Red - suspicious / high risk
}

# Font Definitions  
FONT_SIZES = {
    'tiny': 8,
    'xsmall': 10,
    'small': 12,
    'medium': 14,
    'large': 16,
    'xlarge': 18,
    'title': 20,
    'heading': 24,
}

# Font Families
FONT_FAMILY = {
    'default': 'Segoe UI',      # Windows default  
    'monospace': 'Consolas',    # Monospace font for hex view
    'fixed': 'Courier New'      # Alternative monospace
}

# Spacing Units (in pixels) 
SPACING_UNITS = {
    'xs': 4,
    'sm': 8,
    'md': 12,
    'lg': 16,
    'xl': 20,
    'xxl': 24,
    'xxxl': 32,
}

# Widget Styles
WIDGET_STYLES = {
    # General widget styling
    'default_widget': """
        QWidget {
            background-color: %s;
            color: %s;
            border: 1px solid %s;
        }
    """ % (COLORS['surface'].name(), COLORS['text_primary'].name(), COLORS['border'].name()),
    
    # Button styling  
    'button': """
        QPushButton {
            background-color: %s;
            color: white;
            border: none;
            padding: %dpx %dpx;
            text-align: center;
            font-weight: bold;
            border-radius: %dpx;
        }
        QPushButton:hover {
            background-color: %s;
        }
        QPushButton:pressed {
            background-color: %s;
        }
    """ % (
        COLORS['primary'].name(), 
        SPACING_UNITS['md'], 
        SPACING_UNITS['lg'], 
        4,  # border-radius
        COLORS['primary_dark'].name(),
        COLORS['primary_light'].name()
    ),
    
    'button_primary': """
        QPushButton {
            background-color: %s;
            color: white;
            border: none;
            padding: %dpx %dpx;
            text-align: center;
            font-weight: bold;
            border-radius: %dpx;
        }
        QPushButton:hover {
            background-color: %s;
        }
        QPushButton:pressed {
            background-color: %s;
        }
    """ % (
        COLORS['primary'].name(), 
        SPACING_UNITS['md'], 
        SPACING_UNITS['lg'], 
        4, 
        COLORS['primary_dark'].name(),
        COLORS['primary_light'].name()
    ),
    
    'button_secondary': """
        QPushButton {
            background-color: %s;
            color: white;
            border: none;
            padding: %dpx %dpx;
            text-align: center;
            font-weight: bold;
            border-radius: %dpx;
        }
        QPushButton:hover {
            background-color: %s;
        }
        QPushButton:pressed {
            background-color: %s;
        }
    """ % (
        COLORS['secondary'].name(), 
        SPACING_UNITS['md'], 
        SPACING_UNITS['lg'], 
        4, 
        COLORS['secondary_dark'].name(),
        COLORS['secondary_light'].name()
    ),
    
    # Status bar styling
    'status_bar': """
        QStatusBar {
            background-color: %s;
            color: %s;
            padding: %dpx;
            font-weight: bold;
        }
        QStatusBar::item {
            border: none;
        }
    """ % (
        COLORS['surface'].name(), 
        COLORS['text_primary'].name(),
        SPACING_UNITS['sm']
    ),
    
    # Tab styling
    'tab_widget': """
        QTabWidget::pane {
            border: 1px solid %s;
            background-color: %s;
        }
        QTabBar::tab {
            background-color: %s;
            color: %s;
            padding: %dpx %dpx;
            margin-right: %dpx;
            border-top-left-radius: %dpx;
            border-top-right-radius: %dpx;
        }
        QTabBar::tab:selected {
            background-color: %s;
        }
        QTabBar::tab:hover {
            background-color: %s;
        }
    """ % (
        COLORS['border'].name(),
        COLORS['surface'].name(),
        COLORS['surface_dark'].name(),
        COLORS['text_primary'].name(),
        SPACING_UNITS['md'],
        SPACING_UNITS['lg'],
        4,
        4,
        COLORS['primary'].name(),
        COLORS['primary_light'].name()
    ),
    
    # List widget styling
    'list_widget': """
        QListWidget {
            background-color: %s;
            border: 1px solid %s;
            color: %s;
            padding: %dpx;
        }
        QListWidget::item {
            padding: %dpx;
            margin-bottom: %dpx;
        }
        QListWidget::item:selected {
            background-color: %s;
            color: white;
        }
    """ % (
        COLORS['surface'].name(),
        COLORS['border'].name(),
        COLORS['text_primary'].name(),
        SPACING_UNITS['sm'],
        SPACING_UNITS['md'],
        2,
        COLORS['primary'].name()
    ),
    
    # Progress bar styling
    'progress_bar': """
        QProgressBar {
            border: 1px solid %s;
            text-align: center;
            padding: %dpx;
            background-color: %s;
        }
        QProgressBar::chunk {
            background-color: %s;
            width: %dpx;
        }
    """ % (
        COLORS['border'].name(),
        SPACING_UNITS['sm'],
        COLORS['surface'].name(), 
        COLORS['primary'].name(),
        15
    )
}

# Set application font globally
def setup_application_font():
    """Setup default application font"""
    app = QApplication.instance()
    if app:
        # Try to set the default font 
        font = QFont(FONT_FAMILY['default'], FONT_SIZES['medium'])
        app.setFont(font)
        return font

# Utility functions for styling
def get_color(name):
    """Get color by name from palette"""
    return COLORS.get(name, QColor(0, 0, 0))

def get_font(size='medium', family=None):
    """Get font with specified size and family"""
    if family is None:
        family = FONT_FAMILY['default']
        
    font = QFont(family, FONT_SIZES[size])
    return font

def apply_style(widget, style_name):
    """Apply a predefined style to a widget"""
    style = WIDGET_STYLES.get(style_name)
    if style:
        widget.setStyleSheet(style)

# Get current application font
DEFAULT_FONT = setup_application_font()