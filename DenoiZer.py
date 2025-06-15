import os
import sys
import json
import subprocess
import multiprocessing
import psutil
import OpenImageIO as oiio
# Remplacer OpenEXR et Imath par des alternatives
# import OpenEXR
# import Imath
import time
# Remplacer PySide2 par PySide6
from PySide6.QtWidgets import QComboBox, QGridLayout, QSizePolicy
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog,
    QLineEdit, QTextEdit, QHBoxLayout, QListWidget, QListWidgetItem, QCheckBox,
    QProgressBar, QFrame, QGroupBox, QSplitter, QToolButton, QMessageBox, QScrollArea,
    QSlider, QTabWidget, QMenu
)
from PySide6.QtCore import Qt, QSettings, QPropertyAnimation, QSize, QEvent, QTimer
from PySide6.QtGui import QIcon, QKeyEvent, QFontDatabase, QFont
from ExrMerge import merge_final_exrs
from Integrator_Denoizer import run_integrator_generate

class CollapsibleSection(QWidget):
    """Collapsible section widget with arrow button to show/hide content"""
    
    def __init__(self, title, parent=None, is_logs_section=False):
        super().__init__(parent)
        self.setObjectName("collapsibleSection")
        self.is_logs_section = is_logs_section
        
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Header with title and button
        self.header_widget = QWidget()
        self.header_layout = QHBoxLayout(self.header_widget)
        self.header_layout.setContentsMargins(5, 5, 5, 5)
        
        # Arrow button
        self.toggle_button = QToolButton()
        self.toggle_button.setArrowType(Qt.DownArrow)
        self.toggle_button.setStyleSheet("""
            QToolButton {
                border: none;
                background-color: transparent;
            }
        """)
        self.toggle_button.clicked.connect(self.toggle_content)
        
        # Title label
        self.title_label = QLabel(f"<b>{title}</b>")
        self.title_label.setStyleSheet("""
            QLabel {
                color: #0078d7;
                font-size: 14px;
            }
        """)
        
        # Add widgets to header
        self.header_layout.addWidget(self.toggle_button)
        self.header_layout.addWidget(self.title_label)
        self.header_layout.addStretch()
        
        # Container for content
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(12, 0, 0, 0)  # Left margin for indentation
        
        # Separator line
        self.separator_line = QFrame()
        self.separator_line.setFrameShape(QFrame.HLine)
        self.separator_line.setFrameShadow(QFrame.Sunken)
        self.separator_line.setStyleSheet("background-color: #3c3c3c;")
        
        # Add widgets to main layout
        self.main_layout.addWidget(self.header_widget)
        self.main_layout.addWidget(self.separator_line)
        self.main_layout.addWidget(self.content_widget)
        
        # Initial state
        self.is_collapsed = False
        
    def add_widget(self, widget):
        """Add a widget to the content"""
        self.content_layout.addWidget(widget)
        
    def add_layout(self, layout):
        """Add a layout to the content"""
        self.content_layout.addLayout(layout)
        
    def toggle_content(self):
        """Toggle the display of content"""
        self.is_collapsed = not self.is_collapsed
        
        # Change arrow icon
        if self.is_collapsed:
            self.toggle_button.setArrowType(Qt.RightArrow)
        else:
            self.toggle_button.setArrowType(Qt.DownArrow)
            
        # Show/hide content
        self.content_widget.setVisible(not self.is_collapsed)
        self.separator_line.setVisible(not self.is_collapsed)
        
        # If this is the logs section, emit a resize event to the parent window
        if self.is_logs_section:
            self.parent().adjustSize()

class LogWindow(QWidget):
    """Independent window for logs display"""
    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("DenoiZer - Processing")
        self.resize(800, 400)
        
        # Définir l'icône de la fenêtre
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "DenoiZer_icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # Main layout
        layout = QVBoxLayout(self)
        
        # Status label
        self.status_label = QLabel("Processing...")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #0078d7;")
        layout.addWidget(self.status_label)
        
        # Estimated time label
        self.time_label = QLabel("Estimated time: calculating...")
        self.time_label.setStyleSheet("font-size: 12px; color: #e0e0e0;")
        layout.addWidget(self.time_label)
        
        # Progress bar container
        progress_widget = QWidget()
        progress_layout = QVBoxLayout(progress_widget)
        progress_layout.setContentsMargins(0, 5, 0, 5)
        
        # Progress bar (sans texte "Current task:")
        self.progress = QProgressBar()
        self.progress.setValue(0)
        progress_layout.addWidget(self.progress)
        
        layout.addWidget(progress_widget)
        
        # Emergency stop button dans la fenêtre de log
        self.stop_btn = QPushButton("Stop the process")
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #EF5350;
            }
            QPushButton:pressed {
                background-color: #E53935;
            }
        """)
        self.stop_btn.clicked.connect(self.request_stop)
        
        stop_layout = QHBoxLayout()
        stop_layout.addStretch()
        stop_layout.addWidget(self.stop_btn)
        stop_layout.addStretch()
        layout.addLayout(stop_layout)
        
        # Log output
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)
        
        # Style
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: #e0e0e0;
            }
            QTextEdit {
                background-color: #2d2d2d;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 5px;
            }
            QProgressBar {
                text-align: center;
                height: 20px;
                background-color: #2d2d2d;
                border: none;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #0078d7;
                border-radius: 4px;
            }
        """)
        
        # Timer pour traiter les événements de l'interface
        self.process_events_timer = None
        
    def request_stop(self):
        """Request process to stop"""
        reply = QMessageBox.question(
            self, 
            "Confirm Stop", 
            "Are you sure you want to stop the process? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.append_log("🛑 Stop requested. Terminating process...")
            self.status_label.setText("Stopping...")
            self.stop_btn.setEnabled(False)
            
            # Notify parent about the stop request
            if self.parent():
                self.parent().process_stop_requested()
        
    def append_log(self, message):
        self.log_output.append(message)
        # Auto-scroll to bottom
        self.log_output.verticalScrollBar().setValue(
            self.log_output.verticalScrollBar().maximum()
        )
        # Traiter les événements pour maintenir l'interface réactive
        QApplication.processEvents()
        
    def set_progress(self, value):
        self.progress.setValue(value)
        # Traiter les événements pour maintenir l'interface réactive
        QApplication.processEvents()
        
    def set_overall_progress(self, value):
        # Cette méthode est maintenue pour compatibilité mais redirige vers set_progress
        self.set_progress(value)
        
    def set_status(self, message):
        self.status_label.setText(message)
        # Traiter les événements pour maintenir l'interface réactive
        QApplication.processEvents()
        
    def set_estimated_time(self, time_str):
        self.time_label.setText(f"{time_str}")
        # Traiter les événements pour maintenir l'interface réactive
        QApplication.processEvents()
        
    def reset_controls(self):
        """Reset control buttons to initial state"""
        self.stop_btn.setEnabled(True)
        
    def showEvent(self, event):
        """Appelé lorsque la fenêtre est affichée"""
        super().showEvent(event)
        # Centrer la fenêtre sur l'écran en utilisant la méthode compatible avec PySide6
        screen = QApplication.primaryScreen().geometry()
        center = screen.center()
        frame_geometry = self.frameGeometry()
        frame_geometry.moveCenter(center)
        self.move(frame_geometry.topLeft())
        
        # Reset controls when shown
        self.reset_controls()

class DenoizerTab(QWidget):
    def __init__(self, parent=None, tab_name="Untitled", config=None, settings=None):
        super().__init__(parent)
        self.tab_name = tab_name
        self.config = config
        self.settings = settings
        self.log_window = LogWindow(self)
        
        # Add this line to initialize shadow_mode attribute
        self.shadow_mode = False
        
        # Initialiser l'interface utilisateur (contient la plupart du code actuel de DenoiZer.__init__)
        self.init_ui()
        
    def init_ui(self):
        # Ici, déplacer la majorité du code actuel de DenoiZer.__init__
        # En gardant les mêmes fonctionnalités, mais adapté pour être dans un onglet
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Flags for process control
        self.processing = False
        self.stop_requested = False
        self.pause_requested = False
        self.process = None
        self.process_check_timer = None  # Ajouter cette ligne ici
        
        # S'assurer que use_gpu_checkbox est initialisé à False par défaut
        if not hasattr(self, 'use_gpu_checkbox'):
            self.use_gpu_checkbox = QCheckBox()
            self.use_gpu_checkbox.setChecked(False)
        
        # Emergency container
        self.emergency_container = QWidget()
        emergency_layout = QHBoxLayout(self.emergency_container)
        emergency_layout.setContentsMargins(0, 0, 0, 10)
        self.emergency_stop_btn = QPushButton("Stop the process (ESC)")
        self.emergency_stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #d32f2f;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #f44336;
            }
        """)
        self.emergency_stop_btn.clicked.connect(self.emergency_stop)
        self.emergency_stop_btn.setVisible(False)  # Masqué par défaut
        
        # Container for emergency stop button (toujours au même endroit)
        self.emergency_container = QWidget()
        emergency_layout = QHBoxLayout(self.emergency_container)
        emergency_layout.setContentsMargins(0, 0, 0, 10)
        emergency_layout.addWidget(self.emergency_stop_btn)
        main_layout.addWidget(self.emergency_container)
        self.emergency_container.setVisible(False)  # Masqué par défaut
        
        # Scroll Area pour le contenu principal (tout sauf Actions)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        
        # Widget conteneur pour le scroll area
        scroll_content = QWidget()
        
        # Content layout pour les sections scrollables
        content_layout = QVBoxLayout(scroll_content)
        
        # Modern Dark Style
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: #e0e0e0;
                font-size: 12px;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLineEdit, QTextEdit, QListWidget, QComboBox {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 5px;
            }
            QPushButton {
                background-color: #0078d7;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px;
                min-height: 20px;
                font-weight: bold;
            }
            QPushButton#actionButton {
                min-height: 40px;
            }
            QPushButton#secondaryButton {
                background-color: #6a4c93;
                min-height: 30px;
            }
            QPushButton:hover {
                background-color: #0086f0;
            }
            QPushButton#secondaryButton:hover {
                background-color: #7b5ca3;
            }
            QPushButton:pressed {
                background-color: #005fa3;
            }
            QPushButton#secondaryButton:pressed {
                background-color: #5a3c83;
            }
            QPushButton:disabled {
                background-color: #444444;
                color: #999999;
            }
            QCheckBox {
                spacing: 5px;
            }
            QProgressBar {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: none;
                border-radius: 4px;
                text-align: center;
                height: 12px;
            }
            QProgressBar::chunk {
                background-color: #0078d7;
                border-radius: 4px;
            }
            QGroupBox {
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                margin-top: 1.5em;
                padding-top: 1em;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #0078d7;
            }
            QLabel {
                padding: 2px;
            }
            QSplitter::handle {
                background-color: #3c3c3c;
            }
            QScrollBar:vertical {
                border: none;
                background: #2d2d2d;
                width: 12px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #555555;
                min-height: 20px;
                border-radius: 3px;
            }
            QListWidget {
                alternate-background-color: #252525;
            }
            QComboBox {
                padding: 5px;
                border-radius: 4px;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            #collapsibleSection {
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                margin: 5px 0px;
            }
            #signature {
                color: #666666;
                font-style: italic;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)

        # Settings for input/output paths
        self.settings = QSettings("DenoiZer", "App")

        # Load RenderMan config
        try:
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_config.json")
            with open(config_path, "r") as f:
                self.config = json.load(f)
        except:
            self.config = {
                "COMPRESSION_MODE": "ZIP_COMPRESSION",
                "RENDERMAN_PROSERVER": "",
                "ENABLE_INTEGRATOR": False,  # False par défaut
                "LIGHT_GROUP_PREFIX": "LGT",  # Ajout du préfixe par défaut
                "ENABLE_SHADOWS": False,      # Shadows désactivées par défaut
                "SHADOWS_AOV_NAME": "SHADOWS", # Nom par défaut pour l'AOV des shadows
                "ENABLE_CROSSFRAME": True     # CrossFrame activé par défaut
            }
        
        # Main widgets
        self.input_path = QLineEdit()
        self.output_path = QLineEdit()
        self.aov_list = QListWidget()
        self.integrator_list = QListWidget()
        
        # Working directories section
        self.dirs_section = CollapsibleSection("SETTINGS")
        dirs_content = QWidget()
        dirs_layout = QVBoxLayout(dirs_content)
        
        # Ajouter l'indicateur AOVs en haut à droite du header
        self.aovs_indicator = QLabel("❌ Denoise AOVs")
        self.aovs_indicator.setStyleSheet("""
            QLabel {
                font-size: 12px;
                padding: 2px 5px;
                border-radius: 3px;
                background-color: transparent;
                font-weight: bold;
            }
        """)
        self.aovs_indicator.setToolTip("AOVs de débruitage non détectés")
        self.dirs_section.header_layout.addWidget(self.aovs_indicator)
        
        # Input/Output on a single line
        io_layout = QHBoxLayout()
        
        # Input Folder
        input_group = QWidget()
        input_layout = QHBoxLayout(input_group)
        input_layout.setContentsMargins(0, 0, 10, 0)
        input_layout.addWidget(QLabel("Input:"))
        input_layout.addWidget(self.input_path, 1)
        input_layout.addWidget(self._create_button("Browse", self.select_input_folder))
        io_layout.addWidget(input_group)
        
        # Output Folder
        output_group = QWidget()
        output_layout = QHBoxLayout(output_group)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.addWidget(QLabel("Output:"))
        output_layout.addWidget(self.output_path, 1)
        output_layout.addWidget(self._create_button("Browse", self.select_output_folder))
        io_layout.addWidget(output_group)
        
        dirs_layout.addLayout(io_layout)
        
        # RenderMan Version
        renderman_layout = QHBoxLayout()
        renderman_layout.addWidget(QLabel("RenderMan Version:"))
        self.renderman_path = QLineEdit(self.config.get("RENDERMAN_PROSERVER", ""))
        self.renderman_path.setReadOnly(True)
        renderman_layout.addWidget(self.renderman_path, 1)
        change_renderman_btn = self._create_button("Change", self.change_renderman_version)
        renderman_layout.addWidget(change_renderman_btn)
        dirs_layout.addLayout(renderman_layout)
        

        
        # Compression Mode
        compression_layout = QHBoxLayout()
        compression_layout.addWidget(QLabel("Compression Mode:"))
        self.compression_menu = QComboBox()
        self.compression_menu.addItems(["ZIP", "DWAA", "DWAB", "PIZ", "NO_COMPRESSION"])
        self.compression_menu.setCurrentText("DWAB")
        self.compression_menu.currentIndexChanged.connect(self.update_compression)
        self.selected_compression = "DWAB"
        # Ajouter une icône de flèche au menu déroulant
        self.compression_menu.setStyleSheet("""
            QComboBox {
                padding: 5px;
                border-radius: 4px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left-width: 1px;
                border-left-color: #3c3c3c;
                border-left-style: solid;
                border-top-right-radius: 3px;
                border-bottom-right-radius: 3px;
            }
            QComboBox::down-arrow {
                border-width: 5px;
                border-style: solid;
                border-color: #e0e0e0 transparent transparent transparent;
                width: 0px;
                height: 0px;
            }
        """)
        compression_layout.addWidget(self.compression_menu)
        dirs_layout.addLayout(compression_layout)
        
        # Mode buttons layout (CrossFrame, Integrator, Shadow)
        modes_layout = QHBoxLayout()
        modes_layout.setSpacing(8)  # Espace entre les boutons
        
        # CrossFrame Mode button
        self.crossframe_mode_button = QPushButton("CROSS FRAME")
        self.crossframe_mode_button.setCheckable(True)
        self.crossframe_mode_button.setChecked(self.config.get("ENABLE_CROSSFRAME", True))  # Activé par défaut
        self.crossframe_mode_button.clicked.connect(self.toggle_crossframe_mode)
        self.crossframe_mode_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)  # Prend toute la largeur disponible
        self.crossframe_mode_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;  /* Fond transparent pour Single Frame */
                color: #e0e0e0;
                border: 2px dashed #666666;  /* Contour gris en pointillés */
                border-radius: 4px;
                padding: 4px 8px;
                min-height: 25px;
                font-size: 14px;
                font-weight: bold;
                text-align: center;
            }
            QPushButton:hover {
                background-color: rgba(102, 102, 102, 0.1);  /* Léger survol */
                border: 2px dashed #888888;
            }
            QPushButton:pressed {
                background-color: rgba(102, 102, 102, 0.2);
            }
            QPushButton:checked {
                background-color: transparent;  /* Fond transparent */
                border: 2px solid #0078d7;  /* Contour bleu */
                color: #0078d7;  /* Texte bleu */
            }
            QPushButton:checked:hover {
                background-color: rgba(0, 120, 215, 0.1);  /* Léger survol bleu */
                border: 2px solid #106ebe;
                color: #106ebe;
            }
            QPushButton:checked:pressed {
                background-color: rgba(0, 120, 215, 0.2);
                border: 2px solid #005a9e;
                color: #005a9e;
            }
        """)
        modes_layout.addWidget(self.crossframe_mode_button)
        
        # Integrator Mode button
        self.integrator_mode_button = QPushButton("INTEGRATOR EXR")
        self.integrator_mode_button.setCheckable(True)
        self.integrator_mode_button.setChecked(self.config.get("ENABLE_INTEGRATOR", False))
        self.integrator_mode_button.clicked.connect(self.toggle_integrator_mode)
        self.integrator_mode_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)  # Prend toute la largeur disponible
        self.integrator_mode_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;  /* Fond transparent pour off */
                color: #e0e0e0;
                border: 2px dashed #666666;  /* Contour gris en pointillés */
                border-radius: 4px;
                padding: 4px 8px;
                min-height: 25px;
                font-size: 14px;
                font-weight: bold;
                text-align: center;
            }
            QPushButton:hover {
                background-color: rgba(102, 102, 102, 0.1);  /* Léger survol */
                border: 2px dashed #888888;
            }
            QPushButton:pressed {
                background-color: rgba(102, 102, 102, 0.2);
            }
            QPushButton:checked {
                background-color: transparent;  /* Fond transparent */
                border: 2px solid #388e3c;  /* Contour vert */
                color: #388e3c;  /* Texte vert */
            }
            QPushButton:checked:hover {
                background-color: rgba(56, 142, 60, 0.1);  /* Léger survol vert */
                border: 2px solid #4caf50;
                color: #4caf50;
            }
            QPushButton:checked:pressed {
                background-color: rgba(56, 142, 60, 0.2);
                border: 2px solid #2e7d32;
                color: #2e7d32;
            }
        """)
        modes_layout.addWidget(self.integrator_mode_button)

        # Shadow Mode button
        self.shadow_mode_button = QPushButton("SHADOW MODE")
        self.shadow_mode_button.setCheckable(True)
        self.shadow_mode_button.setChecked(False)
        self.shadow_mode_button.clicked.connect(self.toggle_shadow_mode)
        self.shadow_mode_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)  # Prend toute la largeur disponible
        self.shadow_mode_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;  /* Fond transparent pour off */
                color: #e0e0e0;
                border: 2px dashed #666666;  /* Contour gris en pointillés */
                border-radius: 4px;
                padding: 4px 8px;
                min-height: 25px;
                font-size: 14px;
                font-weight: bold;
                text-align: center;
            }
            QPushButton:hover {
                background-color: rgba(102, 102, 102, 0.1);  /* Léger survol */
                border: 2px dashed #888888;
            }
            QPushButton:pressed {
                background-color: rgba(102, 102, 102, 0.2);
            }
            QPushButton:checked {
                background-color: transparent;  /* Fond transparent */
                border: 2px solid #ffffff;  /* Contour blanc */
                color: #ffffff;  /* Texte blanc */
            }
            QPushButton:checked:hover {
                background-color: rgba(255, 255, 255, 0.1);  /* Léger survol blanc */
                border: 2px solid #f5f5f5;
                color: #f5f5f5;
            }
            QPushButton:checked:pressed {
                background-color: rgba(255, 255, 255, 0.2);
                border: 2px solid #e0e0e0;
                color: #e0e0e0;
            }
        """)
        modes_layout.addWidget(self.shadow_mode_button)
        
        dirs_layout.addLayout(modes_layout)
        
        # Initialiser le texte des boutons
        if self.crossframe_mode_button.isChecked():
            self.crossframe_mode_button.setText("CROSS FRAME")
            self.log_window.append_log("ℹ️ CrossFrame denoising enabled - Temporal coherence will be maintained between frames")
        else:
            self.crossframe_mode_button.setText("SINGLE FRAME")
        
        # Scan for available RenderMan versions
        self.scan_renderman_versions()
        
        self.dirs_section.add_widget(dirs_content)
        content_layout.addWidget(self.dirs_section)
        
        # Light Groups Configuration
        self.light_groups_section = CollapsibleSection("Light Groups Configuration")
        light_groups_content = QWidget()
        light_groups_layout = QVBoxLayout(light_groups_content)
        
        # Light Groups Prefix
        prefix_layout = QHBoxLayout()
        prefix_layout.addWidget(QLabel("Light Group Filter:"))
        self.light_group_prefix = QLineEdit(self.config.get("LIGHT_GROUP_PREFIX", "LGT"))
        self.light_group_prefix.textChanged.connect(self.update_light_groups)
        prefix_layout.addWidget(self.light_group_prefix)
        light_groups_layout.addLayout(prefix_layout)
        
        # Available AOVs list
        light_groups_layout.addWidget(QLabel("Available AOVs:"))
        self.available_aovs = QListWidget()
        self.available_aovs.setSelectionMode(QListWidget.ExtendedSelection)
        self.available_aovs.setAlternatingRowColors(True)
        light_groups_layout.addWidget(self.available_aovs)
        
        # Categorization buttons
        buttons_layout = QHBoxLayout()
        self.add_to_diffuse_btn = QPushButton("Add to Diffuse")
        self.add_to_specular_btn = QPushButton("Add to Specular")
        self.remove_from_categories_btn = QPushButton("Clear All")
        self.remove_from_categories_btn.setStyleSheet("""
            QPushButton {
                background-color: #c8223c;  /* Rouge */
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px;
                min-height: 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e53935;
            }
            QPushButton:pressed {
                background-color: #c62828;
            }
        """)
        self.auto_fill_btn = QPushButton("Auto Fill")
        self.auto_fill_btn.setStyleSheet("""
            QPushButton {
                background-color: #6a4c93;  /* Violet */
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px;
                min-height: 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7b5ca3;
            }
            QPushButton:pressed {
                background-color: #5a3c83;
            }
        """)
        self.add_to_diffuse_btn.clicked.connect(lambda: self.categorize_aovs("diffuse"))
        self.add_to_specular_btn.clicked.connect(lambda: self.categorize_aovs("specular"))
        self.remove_from_categories_btn.clicked.connect(self.remove_from_categories)
        self.auto_fill_btn.clicked.connect(self.auto_fill_categories)
        buttons_layout.addWidget(self.add_to_diffuse_btn)
        buttons_layout.addWidget(self.add_to_specular_btn)
        buttons_layout.addWidget(self.remove_from_categories_btn)
        buttons_layout.addWidget(self.auto_fill_btn)
        light_groups_layout.addLayout(buttons_layout)
        
        # Categorized AOVs lists
        categories_layout = QHBoxLayout()
        
        # Diffuse
        diffuse_content = QWidget()
        diffuse_layout = QVBoxLayout(diffuse_content)
        diffuse_layout.addWidget(QLabel("<b>Diffuse AOVs</b>"))
        self.diffuse_aovs = QListWidget()
        self.diffuse_aovs.setAlternatingRowColors(False)
        diffuse_layout.addWidget(self.diffuse_aovs)
        categories_layout.addWidget(diffuse_content)
        
        # Specular
        specular_content = QWidget()
        specular_layout = QVBoxLayout(specular_content)
        specular_layout.addWidget(QLabel("<b>Specular AOVs</b>"))
        self.specular_aovs = QListWidget()
        self.specular_aovs.setAlternatingRowColors(False)
        specular_layout.addWidget(self.specular_aovs)
        categories_layout.addWidget(specular_content)
        
        light_groups_layout.addLayout(categories_layout)
        self.light_groups_section.add_widget(light_groups_content)
        content_layout.addWidget(self.light_groups_section)
        
        # Collapsible AOVs section
        self.aovs_section = CollapsibleSection("AOVs Selection")
        aovs_content = QWidget()
        aovs_layout = QVBoxLayout(aovs_content)
        
        # Déplacer la case Show Denoise AOVs à côté du titre
        # Ajouter la case à cocher directement dans le header du CollapsibleSection
        header_layout = self.aovs_section.header_layout
        self.show_denoise_checkbox = QCheckBox("Show Denoise AOVs")
        self.show_denoise_checkbox.setChecked(False)  # Maintenant décochée par défaut
        self.show_denoise_checkbox.clicked.connect(self.toggle_show_denoise_aovs)
        header_layout.addWidget(self.show_denoise_checkbox)
        
        # Beauty Build (in its own collapsible section)
        self.beauty_section = CollapsibleSection("Beauty Build")
        self.aov_list.setAlternatingRowColors(False)
        # Augmenter la hauteur du QListWidget pour les AOVs
        self.aov_list.setMinimumHeight(200)
        self.beauty_section.add_widget(self.aov_list)
        aovs_layout.addWidget(self.beauty_section)
        
        # Integrator Separator (in its own collapsible section) - Renommé en Build Integrator
        self.integrator_section = CollapsibleSection("INTEGRATOR EXR")
        self.integrator_list.setAlternatingRowColors(False)
        # Augmenter la hauteur du QListWidget pour les intégrateurs
        self.integrator_list.setMinimumHeight(200)
        self.integrator_section.add_widget(self.integrator_list)
        aovs_layout.addWidget(self.integrator_section)
        self.integrator_section.setVisible(self.integrator_mode_button.isChecked())
        
        # Ajouter aovs_content à aovs_section et aovs_section à content_layout
        self.aovs_section.add_widget(aovs_content)
        content_layout.addWidget(self.aovs_section)
        
        # Shadows Configuration (nouvelle section collapsible) - déplacée en dehors de aovs_section
        self.shadows_section = CollapsibleSection("Shadows Configuration")
        shadows_content = QWidget()
        shadows_layout = QVBoxLayout(shadows_content)
        
        # Ajouter la case à cocher Show Denoise AOVs directement dans le header de shadows_section
        header_layout = self.shadows_section.header_layout
        self.shadows_show_denoise_checkbox = QCheckBox("Show Denoise AOVs")
        self.shadows_show_denoise_checkbox.setChecked(True)  # Cochée par défaut
        self.shadows_show_denoise_checkbox.stateChanged.connect(self.toggle_show_denoise_aovs)
        header_layout.addWidget(self.shadows_show_denoise_checkbox)
        
        # Instruction label
        shadows_layout.addWidget(QLabel("Select Shadow AOVs to process:"))
        
        # Shadow AOVs list
        self.shadows_aov_list = QListWidget()
        self.shadows_aov_list.setAlternatingRowColors(False)
        # Configurer pour affichage en grille comme pour les AOVs normaux
        self.shadows_aov_list.setGridSize(QSize(self.shadows_aov_list.width() // 4, 25))
        self.shadows_aov_list.setFlow(QListWidget.LeftToRight)
        self.shadows_aov_list.setViewMode(QListWidget.IconMode)
        self.shadows_aov_list.setResizeMode(QListWidget.Adjust)
        self.shadows_aov_list.setWrapping(True)
        self.shadows_aov_list.setUniformItemSizes(True)
        self.shadows_aov_list.setStyleSheet("QListWidget { background-color: transparent; border: 1px solid #3c3c3c; }")
        self.shadows_aov_list.setMinimumHeight(150)  # Hauteur minimale pour voir plusieurs éléments
        shadows_layout.addWidget(self.shadows_aov_list)
        
        self.shadows_section.add_widget(shadows_content)
        content_layout.addWidget(self.shadows_section)
        # Cacher la section Shadows Configuration au démarrage
        self.shadows_section.setVisible(False)
        
        # Configurer le scroll area avec son contenu
        scroll_area.setWidget(scroll_content)
        
        # Ajouter le scroll area au layout principal
        main_layout.addWidget(scroll_area, 1)  # Stretch factor 1
        
        # Séparateur entre le contenu scrollable et la section Actions
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("background-color: #3c3c3c;")
        main_layout.addWidget(separator)
        
        # Section Actions toujours visible en bas
        actions_widget = QWidget()
        actions_layout = QVBoxLayout(actions_widget)
        actions_layout.setContentsMargins(0, 5, 0, 0)
        actions_layout.setSpacing(8)
        
        # Bouton DENOIZE avec menu déroulant
        denoize_container = QWidget()
        denoize_container.setMinimumHeight(80)
        denoize_layout = QHBoxLayout(denoize_container)
        denoize_layout.setContentsMargins(0, 0, 0, 0)
        denoize_layout.setSpacing(0)

        # Variable pour suivre la fonction actuelle du bouton
        self.current_button_mode = "DENOIZE"

        # Bouton principal
        self.run_btn = QPushButton("DENOIZE")
        self.run_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.run_btn.clicked.connect(self.run_button_action)  # Nouvelle méthode qui détermine l'action
        
        # Style pour le bouton principal avec police Cute Pixel et texte encore plus agrandi
        # Chercher la fenêtre principale qui contient loaded_font_family
        main_window = self
        while main_window.parent() and not hasattr(main_window, 'loaded_font_family'):
            main_window = main_window.parent()
        
        font_family = getattr(main_window, 'loaded_font_family', 'Courier New')
        self.run_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #0078d7;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px;
                font-family: '{font_family}', 'Courier New', monospace;
                font-size: 64px;
                font-weight: bold;
                text-align: center;
            }}
            QPushButton:hover {{
                background-color: #0086f0;
            }}
            QPushButton:pressed {{
                background-color: #005fa3;
            }}
            QPushButton:disabled {{
                background-color: #444444;
                color: #999999;
            }}
        """)

        # Bouton menu
        self.run_menu_btn = QToolButton()
        self.run_menu_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.run_menu_btn.setPopupMode(QToolButton.InstantPopup)
        self.run_menu_btn.setArrowType(Qt.DownArrow)
        self.run_menu_btn.setStyleSheet("""
            QToolButton {
                border-left: none;
                background-color: #444;
                padding: 0 5px;
            }
            QToolButton:hover {
                background-color: #555;
            }
        """)

        # Créer le menu
        run_menu = QMenu(self.run_menu_btn)
        self.denoize_action = run_menu.addAction("DENOIZE")

        self.build_beauty_action = run_menu.addAction("BUILD BEAUTY")
        self.build_integrator_action = run_menu.addAction("BUILD INTEGRATOR")

        # Connecter les actions pour changer le mode du bouton
        self.denoize_action.triggered.connect(lambda: self.change_button_mode("DENOIZE"))

        self.build_beauty_action.triggered.connect(lambda: self.change_button_mode("BUILD BEAUTY"))
        self.build_integrator_action.triggered.connect(lambda: self.change_button_mode("BUILD INTEGRATOR"))

        # Afficher/masquer l'action integrator selon la configuration
        self.build_integrator_action.setVisible(self.integrator_mode_button.isChecked())

        self.run_menu_btn.setMenu(run_menu)

        # Ajouter les widgets au layout avec un ratio de 19:1
        denoize_layout.addWidget(self.run_btn, 19)  # Ratio 19:1
        denoize_layout.addWidget(self.run_menu_btn, 1)
        
        # Ajouter le container au layout des actions
        actions_layout.addWidget(denoize_container)
        

        
        # Signature déplacée en bas des boutons d'action
        signature_layout = QHBoxLayout()
        signature_layout.addStretch()
        signature = QLabel("Created by Romain Dubec")
        signature.setObjectName("signature")
        signature.setStyleSheet("""
            QLabel#signature {
                color: #666666;
                font-style: italic;
                padding: 5px;
                font-size: 11px;
            }
        """)
        signature_layout.addWidget(signature)
        actions_layout.addLayout(signature_layout)
        
        # Ajouter la section Actions au layout principal
        main_layout.addWidget(actions_widget)
        
        # Load last input/output values
        self.input_path.setText(self.settings.value("input_path", ""))
        self.output_path.setText(self.settings.value("output_path", ""))
        
        # Scan on startup
        if self.input_path.text():
            self.scan_aovs()
        
        # Initialize compression slider visibility
        self.update_compression()

    def _create_button(self, label, func):
        btn = QPushButton(label)
        btn.clicked.connect(func)
        return btn

    def _hline(self, w1, w2):
        h = QHBoxLayout()
        h.addWidget(w1)
        h.addWidget(w2)
        return h

    def toggle_show_denoise_aovs(self):
        """Toggle visibility of denoise AOVs in all lists"""
        # Déterminer quel checkbox a déclenché l'action
        sender = self.sender()
        
        # Utiliser le checkbox approprié selon l'origine de l'appel
        if sender == self.shadows_show_denoise_checkbox:
            show_denoise = self.shadows_show_denoise_checkbox.isChecked()
            list_widgets = [self.shadows_aov_list]
        else:
            show_denoise = self.show_denoise_checkbox.isChecked()
            list_widgets = [self.aov_list, self.integrator_list]

        # Liste des mots-clés qui identifient les Denoise AOVs
        denoise_keywords = [
            "mse", "samplecount", "var", "variance",
            "forward", "backward", "forwards", "zfiltered",
            "normal_mse", "normal_var",
            "diffuse_mse", "specular_mse", "albedo_mse", "albedo_var"
        ]

        # Mettre à jour les listes concernées
        for list_widget in list_widgets:
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                widget = list_widget.itemWidget(item)
                if widget:
                    label = widget.findChild(QLabel)
                    aov_text = label.text()
                    aov_lower = aov_text.lower()
                    
                    # Vérifier si c'est un AOV de denoise
                    is_denoise = any(keyword in aov_lower for keyword in denoise_keywords)
                    
                    # Afficher ou masquer selon l'état de la case à cocher
                    if is_denoise:
                        item.setHidden(not show_denoise)
                        
        # Message de log pour confirmer l'action
        section_name = "Shadow" if sender == self.shadows_show_denoise_checkbox else "AOVs"
        action = "shown" if show_denoise else "hidden"
        self.log_window.append_log(f"ℹ️ Denoise AOVs {action} in the {section_name} section")

    def update_compression(self):
        """Update the selected compression mode"""
        self.selected_compression = self.compression_menu.currentText()
        
        # En cas de DWAA/DWAB, définir une valeur de compression par défaut
        if self.selected_compression in ["DWAA", "DWAB"]:
            self.compression_level = 45  # Valeur par défaut
        
        # Log the change
        self.log_window.append_log(f"🔧 Compression mode set to: {self.selected_compression}")

    def run_only_integrator(self):
        """Run only the integrator separation process"""
        # Reset control flags
        self.stop_requested = False
        
        # Validate paths
        input_path = self.input_path.text()
        output_path = self.output_path.text()
        
        if not input_path or not os.path.isdir(input_path):
            QMessageBox.critical(self, "Invalid Input Path", "Please select a valid input folder.")
            return
        
        if not output_path or not os.path.isdir(output_path):
            QMessageBox.critical(self, "Invalid Output Path", "Please select a valid output folder.")
            return
        
        # Check if selected integrators
        selected_integrators = self.get_checked_integrators()
        if not selected_integrators:
            QMessageBox.critical(self, "No Integrators Selected", 
                               "Please select at least one AOV in the Integrator Separator list.")
            return
        
        # Start processing
        self.log_window.show()
        self.log_window.raise_()  # Forcer la fenêtre au premier plan
        self.log_window.activateWindow()  # Activer la fenêtre
        self.log_window.set_status("3: REBUILD INTEGRATOR - Starting process...")
        self.set_processing_state(True)
        
        # Forcer la mise à jour de l'interface
        QApplication.processEvents()
        
        try:
            # Create integrator directory
            integrator_dir = os.path.join(output_path, "INTEGRATOR")
            os.makedirs(integrator_dir, exist_ok=True)
            
            # Get frames
            frames = sorted([f for f in os.listdir(input_path) if f.endswith(".exr")])
            if not frames:
                QMessageBox.critical(self, "No EXR Files", f"No .exr files found in input folder.")
                return
                
            # Check for early stop
            if self.stop_requested:
                self.log_window.append_log("🛑 Process stopped during preparation.")
                return
                
            # Handle pause if requested
            self.check_pause()
            
            # Create progress callback
            def progress_callback(progress_percent):
                # Check for stop request
                if self.stop_requested:
                    return True  # Signal to stop processing
                    
                # Handle pause if requested
                self.check_pause()
                
                self.log_window.set_progress(int(progress_percent))
                # Forcer la mise à jour de l'interface
                QApplication.processEvents()
                return False  # Signal to continue processing
                
            # Create a log callback that forces UI updates
            def log_callback(message):
                # Check for stop request
                if self.stop_requested:
                    return True  # Signal to stop processing
                    
                self.log_window.append_log(message)
                # Forcer la mise à jour de l'interface
                QApplication.processEvents()
                return False  # Signal to continue processing
            
            start_time = time.time()
            
            # Run integrator separator
            run_integrator_generate(
                input_folder=input_path,
                output_folder=integrator_dir,
                selected_integrators=selected_integrators,
                compression_mode=self.selected_compression,
                compression_level=self.compression_level if self.selected_compression in ["DWAA", "DWAB"] else None,
                log_callback=log_callback,
                progress_callback=progress_callback,
                stop_check=lambda: self.stop_requested,
                use_gpu=False
            )
            
            # Check if process was stopped
            if self.stop_requested:
                self.log_window.append_log("🛑 Process stopped during integrator generation.")
                return
            
            # Calculate elapsed time
            elapsed_time = time.time() - start_time
            if elapsed_time < 60:
                time_str = f"{int(elapsed_time)} seconds"
            elif elapsed_time < 3600:
                time_str = f"{int(elapsed_time/60)} minutes {int(elapsed_time%60)} seconds"
            else:
                time_str = f"{int(elapsed_time/3600)} hours {int((elapsed_time%3600)/60)} minutes"
            
            self.log_window.append_log(f"✅ Integrator separation completed in {time_str}!")
            self.log_window.set_status(f"Process completed in {time_str}")
            self.log_window.set_progress(100)
            
            # Forcer la mise à jour de l'interface
            QApplication.processEvents()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            self.log_window.append_log(f"Error: {str(e)}")
        finally:
            self.set_processing_state(False)

    def run_only_merge(self):
        """Run only the AOV merging process"""
        # Reset control flags
        self.stop_requested = False
        
        # Validate paths
        input_path = self.input_path.text()
        output_path = self.output_path.text()
        
        if not input_path or not os.path.isdir(input_path):
            QMessageBox.critical(self, "Invalid Input Path", "Please select a valid input folder.")
            return

        if not output_path or not os.path.isdir(output_path):
            QMessageBox.critical(self, "Invalid Output Path", "Please select a valid output folder.")
            return
        
        # Check if selected AOVs
        selected_aovs = self.get_checked_aovs()
        if not selected_aovs:
            QMessageBox.critical(self, "No AOVs Selected", 
                               "Please select at least one AOV in the Beauty Build list.")
            return
        
        # Check disk space
        disk_space_ok, disk_space_msg = self.check_disk_space(output_path)
        if not disk_space_ok:
            result = QMessageBox.warning(self, "Low Disk Space", 
                                    f"{disk_space_msg}\n\nContinue anyway?",
                                    QMessageBox.Yes | QMessageBox.No)
            if result == QMessageBox.No:
                return
        
        # Start processing
        self.log_window.show()
        self.log_window.raise_()  # Forcer la fenêtre au premier plan
        self.log_window.activateWindow()  # Activer la fenêtre
        self.log_window.set_status("2: REBUILD BEAUTY - Starting process...")
        self.set_processing_state(True)
        
        # Forcer la mise à jour de l'interface
        QApplication.processEvents()
        
        try:
            # Create beauty directory
            beauty_dir = os.path.join(output_path, "BEAUTY")
            os.makedirs(beauty_dir, exist_ok=True)
            
            # Log disk space info
            _, disk_space_msg = self.check_disk_space(output_path)
            self.log_window.append_log(f"💾 {disk_space_msg}")
            
            # Get frames
            frames = sorted([f for f in os.listdir(input_path) if f.endswith(".exr")])
            if not frames:
                QMessageBox.critical(self, "No EXR Files", f"No .exr files found in input folder.")
                return
            
            # Validate AOVs
            if not self.validate_aovs(input_path, selected_aovs):
                return
                
            # Check for early stop
            if self.stop_requested:
                self.log_window.append_log("🛑 Process stopped during preparation.")
                return
                
            # Handle pause if requested
            self.check_pause()
            
            # Create progress callback
            def progress_callback(progress_percent):
                # Check for stop request
                if self.stop_requested:
                    return True  # Signal to stop processing
                    
                # Handle pause if requested
                self.check_pause()
                
                self.log_window.set_progress(int(progress_percent))
                # Forcer la mise à jour de l'interface
                QApplication.processEvents()
                return False  # Signal to continue processing
            
            start_time = time.time()
            
            # Create a log callback that forces UI updates
            def log_callback(message):
                # Check for stop request
                if self.stop_requested:
                    return True  # Signal to stop processing
                    
                self.log_window.append_log(message)
                # Forcer la mise à jour de l'interface
                QApplication.processEvents()
                return False  # Signal to continue processing
            
            # Run merge
            merge_final_exrs(
                output_folder=beauty_dir,
                frame_list=frames,
                input_folder=input_path,
                selected_aovs=selected_aovs,
                compression_mode=self.selected_compression,
                compression_level=self.compression_level if self.selected_compression in ["DWAA", "DWAB"] else None,
                log_callback=log_callback,
                progress_callback=progress_callback,
                shadow_mode=self.shadow_mode,
                shadow_aovs=self.get_checked_shadow_aovs() if self.shadow_mode else [],
                stop_check=lambda: self.stop_requested,
                use_gpu=False
            )
            
            # Check if process was stopped
            if self.stop_requested:
                self.log_window.append_log("🛑 Process stopped during merging.")
                return
            
            # Calculate elapsed time
            elapsed_time = time.time() - start_time
            if elapsed_time < 60:
                time_str = f"{int(elapsed_time)} seconds"
            elif elapsed_time < 3600:
                time_str = f"{int(elapsed_time/60)} minutes {int(elapsed_time%60)} seconds"
            else:
                time_str = f"{int(elapsed_time/3600)} hours {int((elapsed_time%3600)/60)} minutes"
            
            self.log_window.append_log(f"✅ AOV merging completed in {time_str}!")
            self.log_window.set_status(f"Process completed in {time_str}")
            self.log_window.set_progress(100)
            
            # Forcer la mise à jour de l'interface
            QApplication.processEvents()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            self.log_window.append_log(f"Error: {str(e)}")
        finally:
            self.set_processing_state(False)

    def select_input_folder(self):
        # Utilisation de la fenêtre standard Windows Explorer
        folder = QFileDialog.getExistingDirectory(self, "Choose input folder")
        if folder:
            self.input_path.setText(folder)
            self.settings.setValue("input_path", folder)
            # Effacer les fichiers sélectionnés précédemment
            if hasattr(self, 'selected_files'):
                delattr(self, 'selected_files')
            self.input_path.setToolTip("")
            self.scan_aovs()

    def select_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose output folder")
        if folder:
            self.output_path.setText(folder)
            self.settings.setValue("output_path", folder)

    def check_denoise_aovs(self, aovs_list):
        """Vérifier si les AOVs nécessaires pour le débruitage sont présents"""
        required_aovs = ["mse", "normal", "albedo", "diffuse", "specular"]
        optional_aovs = ["samplecount", "var", "variance", "forward", "backward", "zfiltered"]
        
        found_required = []
        found_optional = []
        
        for aov in aovs_list:
            aov_lower = aov.lower()
            for req in required_aovs:
                if req in aov_lower:
                    found_required.append(req)
                    break
            for opt in optional_aovs:
                if opt in aov_lower:
                    found_optional.append(opt)
                    break
        
        # Vérifier si on a au moins les AOVs de base
        has_mse = any("mse" in aov.lower() for aov in aovs_list)
        has_normal = any("normal" in aov.lower() for aov in aovs_list)
        has_basic_aovs = any(aov.lower() in ["albedo", "diffuse", "specular", "ci"] for aov in aovs_list)
        
        # Mettre à jour l'indicateur
        if has_mse and has_normal and has_basic_aovs:
            self.aovs_indicator.setText("✅ Denoise AOVs")
            self.aovs_indicator.setStyleSheet("""
                QLabel {
                    font-size: 12px;
                    padding: 2px 5px;
                    border-radius: 3px;
                    background-color: transparent;
                    color: #4CAF50;
                    font-weight: bold;
                }
            """)
            self.aovs_indicator.setToolTip(f"AOVs de débruitage détectés: {', '.join(found_required + found_optional)}")
        else:
            self.aovs_indicator.setText("❌ Denoise AOVs")
            self.aovs_indicator.setStyleSheet("""
                QLabel {
                    font-size: 12px;
                    padding: 2px 5px;
                    border-radius: 3px;
                    background-color: transparent;
                    color: #F44336;
                    font-weight: bold;
                }
            """)
            missing = []
            if not has_mse:
                missing.append("MSE")
            if not has_normal:
                missing.append("Normal")
            if not has_basic_aovs:
                missing.append("AOVs de base (albedo/diffuse/specular)")
            self.aovs_indicator.setToolTip(f"AOVs manquants: {', '.join(missing)}")

    def scan_aovs(self):
        folder = self.input_path.text().split(" (")[0]  # Extraire le chemin du dossier sans la partie "(X files selected)"
        if not folder or not os.path.isdir(folder):
            # Réinitialiser l'indicateur si pas de dossier
            self.aovs_indicator.setText("❌ Denoise AOVs")
            self.aovs_indicator.setToolTip("Aucun dossier sélectionné")
            return

        self.aov_list.clear()
        self.integrator_list.clear()
        self.available_aovs.clear()

        # Utiliser les fichiers sélectionnés s'ils existent, sinon tous les fichiers EXR du dossier
        if hasattr(self, 'selected_files') and self.selected_files:
            files = [f for f in self.selected_files if f.endswith(".exr")]
        else:
            files = sorted([f for f in os.listdir(folder) if f.endswith(".exr")])  # Fixed indentation here
        
        if not files:
            self.log_window.append_log("❌ No .exr files found in directory.")
            return

        first_file = os.path.join(folder, files[0])
        inp = oiio.ImageInput.open(first_file)
        if not inp:
            self.log_window.append_log("❌ Error opening: " + first_file)
            return

        channels = inp.spec().channelnames
        inp.close()

        grouped = {}
        for ch in channels:
            base = ch.rsplit('.', 1)[0] if '.' in ch else ch
            grouped.setdefault(base, 0)
            grouped[base] += 1

        self.all_aovs = sorted(grouped)
        prefix = self.light_group_prefix.text().upper()

        show_denoise = self.show_denoise_checkbox.isChecked()

        denoise_keywords = [
            "mse", "samplecount", "var",
            "forward_extra", "backward_extra", "forwards_extra", "zfiltered",
            "normal", "normal_mse", "normal_var",
            "diffuse_mse", "specular_mse", "albedo_mse", "albedo_var"
        ]

        # List of AOVs to exclude from Beauty Build
        beauty_exclude = ["__depth", "__st", "__nworld", "__pworld"]
        # List of AOVs to exclude from Integrator Separator
        integrator_exclude = ["Ci", "diffuse", "specular", "albedo", "subsurface"]
        # List of AOVs to check by default in Beauty Build
        beauty_default_checked = ["a", "Ci", "albedo", "diffuse", "specular", "subsurface"]
        # List of AOVs to check by default in Integrator Separator
        integrator_default_checked = ["nn", "__depth", "depth", "__st", "__nworld", "__pworld"]
        
        # Créer une liste des AOVs dans les light groups pour les exclure des listes Beauty et Integrator
        light_group_aovs = []
        for i in range(self.diffuse_aovs.count()):
            light_group_aovs.append(self.diffuse_aovs.item(i).text())
        for i in range(self.specular_aovs.count()):
            light_group_aovs.append(self.specular_aovs.item(i).text())

        # Configure pour 4 colonnes
        self.aov_list.setGridSize(QSize(self.aov_list.width() // 4, 25))
        self.aov_list.setFlow(QListWidget.LeftToRight)
        self.aov_list.setViewMode(QListWidget.IconMode)
        self.aov_list.setResizeMode(QListWidget.Adjust)
        self.aov_list.setWrapping(True)
        self.aov_list.setUniformItemSizes(True)
        # Supprimer le fond alterné des lignes
        self.aov_list.setAlternatingRowColors(False)
        self.aov_list.setStyleSheet("QListWidget { background-color: transparent; border: 1px solid #3c3c3c; }")
        
        self.integrator_list.setGridSize(QSize(self.integrator_list.width() // 4, 25))
        self.integrator_list.setFlow(QListWidget.LeftToRight)
        self.integrator_list.setViewMode(QListWidget.IconMode)
        self.integrator_list.setResizeMode(QListWidget.Adjust)
        self.integrator_list.setWrapping(True)
        self.integrator_list.setUniformItemSizes(True)
        # Supprimer le fond alterné des lignes
        self.integrator_list.setAlternatingRowColors(False)
        self.integrator_list.setStyleSheet("QListWidget { background-color: transparent; border: 1px solid #3c3c3c; }")

        def create_aov_item(aov, is_denoise=False, default_checked=False):
            item_widget = QWidget()
            item_layout = QHBoxLayout(item_widget)
            item_layout.setContentsMargins(5, 0, 5, 0)
            
            # Checkbox on left
            checkbox = QCheckBox()
            checkbox.setChecked(default_checked)
            item_layout.addWidget(checkbox)
            
            # Label with AOV name
            label = QLabel(aov)
            if is_denoise:
                label.setStyleSheet("color: gray;")
            item_layout.addWidget(label)
            
            # Stretch to push content to left
            item_layout.addStretch()
            
            list_item = QListWidgetItem()
            if is_denoise and not show_denoise:
                list_item.setHidden(True)
            list_item.setSizeHint(QSize(self.aov_list.width() // 4 - 10, 25))
            
            return list_item, item_widget

        for aov in self.all_aovs:
            aov_lower = aov.lower()
            aov_upper = aov.upper()
            is_denoise = any(keyword in aov_lower for keyword in denoise_keywords)
            is_light_group = prefix and aov_upper.startswith(prefix)
            
            # Vérifier si l'AOV est dans les light groups
            is_in_light_groups = aov in light_group_aovs

            # -- BEAUTY LIST - Inclure les AOVs de light group qui ne sont pas encore dans les tableaux
            if not any(aov.startswith(exclude) for exclude in beauty_exclude) and (not is_in_light_groups):
                list_item, item_widget = create_aov_item(
                    aov,
                    is_denoise=is_denoise,
                    default_checked=aov in beauty_default_checked
                )
                self.aov_list.addItem(list_item)
                self.aov_list.setItemWidget(list_item, item_widget)

            # -- INTEGRATOR LIST - Inclure les AOVs de light group qui ne sont pas encore dans les tableaux
            if not any(aov.startswith(exclude) for exclude in integrator_exclude) and (not is_in_light_groups):
                list_item, item_widget = create_aov_item(
                    aov,
                    is_denoise=is_denoise,
                    default_checked=any(keyword in aov_lower for keyword in integrator_default_checked)
                )
                self.integrator_list.addItem(list_item)
                self.integrator_list.setItemWidget(list_item, item_widget)

            # -- AVAILABLE AOVs for Light Groups - Inclure tous les AOVs qui correspondent au préfixe
            if not prefix or (prefix and aov_upper.startswith(prefix)):
                self.available_aovs.addItem(aov)

        # Auto-fill light groups une seule fois lors de l'initialisation
        # Vérifier si c'est le premier chargement
        if not hasattr(self, '_initial_load_done'):
            # Ne plus faire d'auto-fill au démarrage
            # self.auto_fill_categories()
            self._initial_load_done = True
            
        # Assurez-vous que les Denoise AOVs sont correctement hidden/shown selon l'état initial de la case
        self.toggle_show_denoise_aovs()
        
        # Vérifier les AOVs nécessaires pour le débruitage
        self.check_denoise_aovs(self.all_aovs)

        # Configuration pour la liste des AOVs d'ombres
        # Remplir la liste des AOVs d'ombres
        self.shadows_aov_list.clear()
        
        # Shadow AOVs defaults - check for common shadow AOV names
        shadow_keywords = ["shadow", "shad", "occlusion", "occ", "ao", "sh"]
        
        # Récupérer l'état de la case Show Denoise AOVs pour les ombres
        show_shadows_denoise = self.shadows_show_denoise_checkbox.isChecked()
        
        for aov in self.all_aovs:
            aov_lower = aov.lower()
            is_denoise = any(keyword in aov_lower for keyword in denoise_keywords)
            # Vérifier si l'AOV est potentiellement une ombre
            is_shadow = any(keyword in aov_lower for keyword in shadow_keywords)
            
            list_item, item_widget = create_aov_item(
                aov,
                is_denoise=is_denoise,
                default_checked=is_shadow
            )
            
            # Masquer les Denoise AOVs selon l'état de la case à cocher
            if is_denoise and not show_shadows_denoise:
                list_item.setHidden(True)
                
            self.shadows_aov_list.addItem(list_item)
            self.shadows_aov_list.setItemWidget(list_item, item_widget)

    def update_light_groups(self):
        """Met à jour la liste des AOVs disponibles basée sur le filtre LGT"""
        filter_text = self.light_group_prefix.text().upper()
        self.available_aovs.clear()
        
        # Ne pas vider les listes diffuse et specular
        # self.diffuse_aovs.clear()
        # self.specular_aovs.clear()
        
        # Sauvegarder le préfixe dans la configuration
        self.config["LIGHT_GROUP_PREFIX"] = filter_text
        self.save_config()

        for aov in self.all_aovs:
            aov_upper = aov.upper()
            # Si le filtre est vide, afficher toutes les AOVs
            # Ou si le filtre est contenu dans le nom de l'AOV (pas seulement au début)
            if not filter_text or (filter_text and filter_text in aov_upper):
                self.available_aovs.addItem(aov)
                # Ne plus faire de catégorisation automatique ici
                # if "DIFFUSE" in aov_upper or "DIF" in aov_upper:
                #     self.diffuse_aovs.addItem(aov)
                # elif "SPECULAR" in aov_upper or "SPEC" in aov_upper:
                #     self.specular_aovs.addItem(aov)

    def auto_fill_categories(self):
        """Remplit automatiquement les catégories diffuse et specular basées sur les noms des AOVs"""
        prefix = self.light_group_prefix.text().upper()
        
        # Vider d'abord les listes
        self.diffuse_aovs.clear()
        self.specular_aovs.clear()
        
        # Parcourir les AOVs disponibles et les catégoriser
        for i in range(self.available_aovs.count()):
            aov = self.available_aovs.item(i).text()
            aov_upper = aov.upper()
            
            # Catégorisation automatique
            if "DIFFUSE" in aov_upper or "DIF" in aov_upper:
                self.diffuse_aovs.addItem(aov)
                self.log_window.append_log(f"✅ {aov} auto-added to diffuse category")
            elif "SPECULAR" in aov_upper or "SPEC" in aov_upper:
                self.specular_aovs.addItem(aov)
                self.log_window.append_log(f"✅ {aov} auto-added to specular category")
        
        self.log_window.append_log(f"✅ Auto Fill complete")
        
        # Actualiser les listes Beauty et Integrator après la modification
        self.update_aov_lists_after_light_group_change()

    def categorize_aovs(self, category):
        selected_items = self.available_aovs.selectedItems()
        target_list = self.diffuse_aovs if category == "diffuse" else self.specular_aovs
        
        for item in selected_items:
            # Vérifier si l'AOV n'est pas déjà dans l'autre catégorie
            other_list = self.specular_aovs if category == "diffuse" else self.diffuse_aovs
            other_items = [other_list.item(i).text() for i in range(other_list.count())]
            
            if item.text() not in other_items:
                # Vérifier si l'AOV n'est pas déjà dans la catégorie cible
                if not any(target_list.item(i).text() == item.text() for i in range(target_list.count())):
                    target_list.addItem(item.text())
                    self.log_window.append_log(f"✅ {item.text()} added to {category} category")
        
        # Actualiser les listes Beauty et Integrator après la modification
        self.update_aov_lists_after_light_group_change()

    def remove_from_categories(self):
        # Vider complètement les deux listes
        diffuse_count = self.diffuse_aovs.count()
        specular_count = self.specular_aovs.count()
        
        # Vider la liste diffuse
        self.diffuse_aovs.clear()
        
        # Vider la liste specular
        self.specular_aovs.clear()
        
        # Log du nombre d'éléments supprimés
        total_removed = diffuse_count + specular_count
        if total_removed > 0:
            self.log_window.append_log(f"🗑️ Cleared all light groups: {diffuse_count} diffuse + {specular_count} specular AOVs removed")
        else:
            self.log_window.append_log("ℹ️ Light group lists were already empty")
        
        # Actualiser les listes Beauty et Integrator après la modification
        self.update_aov_lists_after_light_group_change()

    def find_renderman_path(self):
        base = "C:/Program Files/Pixar"
        if not os.path.isdir(base):
            return None
        versions = sorted([v for v in os.listdir(base) if v.startswith("RenderManProServer")])
        return os.path.join(base, versions[-1]) if versions else None

    def get_checked_items(self, list_widget):
        """Get checked items from a list widget with custom widgets"""
        checked_items = []
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if not item.isHidden():  # Ne considérer que les éléments visibles
                widget = list_widget.itemWidget(item)
                if widget:
                    checkbox = widget.findChild(QCheckBox)
                    if checkbox and checkbox.isChecked():
                        label = widget.findChild(QLabel)
                        checked_items.append(label.text())
        return checked_items

    def get_checked_aovs(self):
        """Get checked AOVs from the Beauty Build list"""
        return self.get_checked_items(self.aov_list)

    def get_checked_integrators(self):
        """Get checked items from the Integrator list"""
        return self.get_checked_items(self.integrator_list)

    def get_light_groups_config(self):
        return {
            "prefix": self.light_group_prefix.text(),
            "diffuse": [self.diffuse_aovs.item(i).text() for i in range(self.diffuse_aovs.count())],
            "specular": [self.specular_aovs.item(i).text() for i in range(self.specular_aovs.count())]
        }

    def run_denoise(self, batch_mode=False):
        """Run the denoising process"""
        # Vérifier si c'est un bouton "DENOIZE ALL" et que nous ne sommes pas en mode batch
        if self.run_btn.text() == "DENOIZE ALL" and not batch_mode:
            # Trouver la fenêtre principale et déclencher le traitement par lot
            parent = self.parent()
            while parent and not hasattr(parent, 'run_all_tabs'):
                parent = parent.parent()
                
            if parent and hasattr(parent, 'run_all_tabs'):
                # S'assurer que nous n'avons pas d'attributs batch qui pourraient interférer
                if hasattr(self, 'batch_tab_index'):
                    delattr(self, 'batch_tab_index')
                if hasattr(self, 'batch_finished_callback'):
                    delattr(self, 'batch_finished_callback')
                    
                parent.run_all_tabs()
                return
        
        # Code existant de run_denoise pour un seul onglet
        # Reset control flags
        self.stop_requested = False
        
        # Validate inputs
        input_path = self.input_path.text()
        output_path = self.output_path.text()
        
        if not input_path or not os.path.isdir(input_path):
            QMessageBox.critical(self, "Invalid Input Path", "Please select a valid input folder.")
            return
        
        if not output_path or not os.path.isdir(output_path):
            QMessageBox.critical(self, "Invalid Output Path", "Please select a valid output folder.")
            return
        
        # Check disk space
        disk_space_ok, disk_space_msg = self.check_disk_space(output_path)
        if not disk_space_ok:
            result = QMessageBox.warning(self, "Low Disk Space", 
                                    f"{disk_space_msg}\n\nContinue anyway?",
                                    QMessageBox.Yes | QMessageBox.No)
            if result == QMessageBox.No:
                return
        
        # Validate RenderMan
        if not self.validate_renderman():
            return
        
        # Get selected AOVs and validate
        selected_aovs = self.get_checked_aovs()
        if not selected_aovs:
            QMessageBox.critical(self, "No AOVs Selected", "Please select at least one AOV to denoise.")
            return
        
        if not self.validate_aovs(input_path, selected_aovs):
            return
        
        # Start denoising
        self.log_window.show()
        self.log_window.raise_()  # Forcer la fenêtre au premier plan
        self.log_window.activateWindow()  # Activer la fenêtre
        self.log_window.set_status("1: DENOISING RENDERMAN - Starting process...")
        self.set_processing_state(True)
        
        try:
            # Setup phases and progress distribution
            phases = {
                "preparation": {"weight": 5, "start": 0, "end": 5},
                "denoising": {"weight": 50, "start": 5, "end": 55},
                "merging": {"weight": 30, "start": 55, "end": 85},
                "integrators": {"weight": 15, "start": 85, "end": 100}
            }
            
            # Définir les étapes globales et leur progression
            global_phases = {
                "preparation": 1,         # 1% quand config.json est créé
                "denoising_albedo": 15,   # 15% quand l'étape albedo est terminée
                "denoising_subsurface": 25, # 25% quand l'étape subsurface est terminée
                "denoising_diffuse": 35,  # 35% quand l'étape diffuse est terminée
                "denoising_done": 50,     # 50% quand le débruitage est terminé
                "merging_done": 75,       # 75% quand la fusion est terminée
                "integrators_done": 100   # 100% quand tout est terminé
            }
            
            frames = sorted([f for f in os.listdir(input_path) if f.endswith(".exr")])
            if not frames:
                self.log_window.append_log("❌ No .exr files found in the input folder.")
                return

            # Phase: preparation (5%)
            self.log_window.set_status("1: DENOISING RENDERMAN - Preparing configuration...")
            self.log_window.set_overall_progress(0)  # Initialiser la barre globale à 0%
            
            # Forcer la mise à jour de l'interface
            QApplication.processEvents()
            
            # Check for early stop
            if self.stop_requested:
                self.log_window.append_log("🛑 Process stopped during preparation.")
                return
            
            # Log disk space info
            _, disk_space_msg = self.check_disk_space(output_path)
            self.log_window.append_log(f"💾 {disk_space_msg}")
            
            # Create output subdirectories
            beauty_dir = os.path.join(output_path, "BEAUTY")
            temp_dir = os.path.join(output_path, "temp_denoised")
            
            # Create directories
            os.makedirs(beauty_dir, exist_ok=True)
            os.makedirs(temp_dir, exist_ok=True)
            
            self.log_window.append_log(f"✅ Created output directory: BEAUTY")
            
            # Create integrator directory only if enabled
            integrator_dir = None
            if self.integrator_mode_button.isChecked():
                integrator_dir = os.path.join(output_path, "INTEGRATOR")
                os.makedirs(integrator_dir, exist_ok=True)
                self.log_window.append_log(f"✅ Created output directory: INTEGRATOR")
            else:
                self.log_window.append_log(f"ℹ️ Build Integrator disabled - INTEGRATOR directory not created")
            
            # Get light groups configuration
            light_groups_config = self.get_light_groups_config()
            prefix = light_groups_config["prefix"]
            
            # En mode shadow, on traite différemment
            if self.shadow_mode:
                # En mode shadow, on sélectionne tous les AOVs pour le denoising
                selected_aovs = self.all_aovs.copy() if hasattr(self, 'all_aovs') else []
                self.log_window.append_log(f"🔍 Shadow Mode: Processing all {len(selected_aovs)} AOVs")
                # S'assurer que les AOVs des shadows sont bien dans la liste
                shadow_aovs = self.get_checked_shadow_aovs()
                for shadow_aov in shadow_aovs:
                    if shadow_aov not in selected_aovs:
                        selected_aovs.append(shadow_aov)
                        self.log_window.append_log(f"➕ Added shadow AOV '{shadow_aov}' to processing list")
            else:
                # Mode normal: utiliser les AOVs sélectionnés par l'utilisateur
                selected_aovs = self.get_checked_aovs()
                if not selected_aovs:
                    QMessageBox.critical(self, "No AOVs Selected", "Please select at least one AOV to denoise.")
                    return
            
            # Automatically add light group AOVs to selection
            selected_aovs.extend(light_groups_config["diffuse"])
            selected_aovs.extend(light_groups_config["specular"])
            
            # Find RenderMan path
            renderman_path = self.config.get("RENDERMAN_PROSERVER")
            self.log_window.append_log(f"🛠️ Using RenderMan: {renderman_path}")
            
            # Check for early stop
            if self.stop_requested:
                self.log_window.append_log("🛑 Process stopped during preparation.")
                return
                
            # Handle pause if requested
            self.check_pause()
            
            # Prepare denoise configuration
            # Choisir les fichiers de paramètres selon l'état du CrossFrame
            if self.crossframe_mode_button.isChecked():
                # CrossFrame activé : utiliser les paramètres optimisés pour le débruitage temporel
                param = os.path.join(renderman_path, "lib", "denoise", "20970-renderman.param").replace("\\", "/")
                topo = os.path.join(renderman_path, "lib", "denoise", "full_w7_4sv2_sym_gen2.topo").replace("\\", "/")
                self.log_window.append_log("🔧 Using CrossFrame optimized parameters: 20970-renderman.param & full_w7_4sv2_sym_gen2.topo")
            else:
                # CrossFrame désactivé : utiliser les paramètres standard
                param = os.path.join(renderman_path, "lib", "denoise", "20973-renderman.param").replace("\\", "/")
                topo = os.path.join(renderman_path, "lib", "denoise", "full_w1_5s_sym_gen2.topo").replace("\\", "/")
                self.log_window.append_log("🔧 Using standard parameters: 20973-renderman.param & full_w1_5s_sym_gen2.topo")

            config = {
                "primary": [os.path.join(input_path, f).replace("\\", "/") for f in frames],
                "aux": {
                    "diffuse": [],
                    "specular": [],
                    "albedo": [{"paths": [os.path.join(input_path, f).replace("\\", "/") for f in frames], "layers": ["albedo"]}],
                    "Ci": [{"paths": [os.path.join(input_path, f).replace("\\", "/") for f in frames], "layers": ["Ci"]}],
                    "subsurface": [{"paths": [os.path.join(input_path, f).replace("\\", "/") for f in frames], "layers": ["subsurface"]}]
                },
                "config": {
                    "passes": selected_aovs,
                    "topology": topo,
                    "parameters": param,
                    "output-dir": temp_dir.replace("\\", "/"),
                    "flow": self.crossframe_mode_button.isChecked(),  # CrossFrame flow
                    "debug": False,
                    "asymmetry": 0.0
                }
            }
            
            # Log whether CrossFrame is enabled
            if self.crossframe_mode_button.isChecked():
                self.log_window.append_log("✅ CrossFrame denoising enabled - Better temporal coherence between frames")
            else:
                self.log_window.append_log("ℹ️ CrossFrame denoising disabled - Each frame processed independently")

            # Add light groups to appropriate categories
            for aov in selected_aovs:
                if aov in light_groups_config["diffuse"]:
                    config["aux"]["diffuse"].append({
                        "paths": config["primary"],
                        "layers": [aov]
                    })
                elif aov in light_groups_config["specular"]:
                    config["aux"]["specular"].append({
                        "paths": config["primary"],
                        "layers": [aov]
                    })
                # Add subsurface to diffuse category if found in selected AOVs
                elif aov == "subsurface":
                    config["aux"]["diffuse"].append({
                        "paths": config["primary"],
                        "layers": ["subsurface"]
                    })
            
            # Add shadows to diffuse category if enabled
            if self.shadow_mode:
                shadow_aovs = self.get_checked_shadow_aovs()
                for shadow_aov in shadow_aovs:
                    if shadow_aov in selected_aovs:
                        config["aux"]["diffuse"].append({
                            "paths": config["primary"],
                            "layers": [shadow_aov]
                        })
                        self.log_window.append_log(f"✅ Added shadow AOV '{shadow_aov}' to diffuse category for denoising")
            
            # Write config file
            config_path = os.path.join(output_path, "config.json")
            with open(config_path, "w") as f:
                json.dump(config, f, indent=4)

            self.log_window.append_log(f"✅ Configuration file written to: {config_path}")
            self.log_window.set_progress(phases["preparation"]["end"])
            self.log_window.set_overall_progress(global_phases["preparation"])  # 1% quand config.json est créé
            
            # Forcer la mise à jour de l'interface
            QApplication.processEvents()
            
            # Check for early stop
            if self.stop_requested:
                self.log_window.append_log("🛑 Process stopped after configuration.")
                return
                
            # Handle pause if requested
            self.check_pause()
            
            # Phase: denoising (50%)
            self.log_window.set_status("1: DENOISING RENDERMAN - Running RenderMan Denoiser...")
            
            # Estimate total time based on frame count
            # Empirical formula: ~10 seconds per frame for denoising, ~3 seconds for merging, ~2 seconds for integrators
            # Multiplier par 3 pour les étapes albedo, diffuse, specular
            frame_count = len(frames)
            total_steps = frame_count * 3  # 3 étapes par frame: albedo, diffuse, specular
            estimated_denoise_time = frame_count * 10 * 3  # Ajusté pour les 3 étapes
            estimated_merge_time = frame_count * 3
            estimated_integrator_time = frame_count * 2
            
            # Adjust time if integrator is disabled
            if not self.integrator_mode_button.isChecked():
                total_estimated_time = estimated_denoise_time + estimated_merge_time
            else:
                total_estimated_time = estimated_denoise_time + estimated_merge_time + estimated_integrator_time
            
            # Format estimated time
            if total_estimated_time < 60:
                time_str = f"{int(total_estimated_time)} seconds"
            elif total_estimated_time < 3600:
                time_str = f"{int(total_estimated_time/60)} minutes {int(total_estimated_time%60)} seconds"
            else:
                time_str = f"{int(total_estimated_time/3600)} hours {int((total_estimated_time%3600)/60)} minutes"
            
            self.log_window.set_estimated_time(time_str)
            
            # Forcer la mise à jour de l'interface
            QApplication.processEvents()
            
            # Run denoiser
            denoise_exe = os.path.join(renderman_path, "bin", "denoise_batch.exe")
            
            # Construire la commande avec le flag -f si CrossFrame est activé
            command = [denoise_exe]
            
            # Ajouter les flags appropriés
            if self.crossframe_mode_button.isChecked():
                command.extend(["-cf", "-f"])
            
            # Optimisations de performance pour denoise_batch
            # Note: L'argument -t pour les threads n'est pas supporté par denoise_batch
            # RenderMan gère automatiquement les threads selon les ressources disponibles
            cpu_count = multiprocessing.cpu_count()
            self.log_window.append_log(f"💻 System has {cpu_count} CPU cores available for RenderMan")
            
            # Supprimer le système de tuiles pour un traitement plus fluide
            # RenderMan traitera l'image entière d'un coup pour de meilleures performances
            self.log_window.append_log("🔧 Processing full image without tiling for optimal performance")
            
            # Optimisations supplémentaires supportées par RenderMan
            # Activer le mode verbose pour un meilleur suivi du progrès
            command.extend(["-v"])
            
            # Ajouter le fichier de configuration JSON (toujours nécessaire)
            command.extend(["-j", config_path])
            
            # Message de log approprié
            log_message = f"🚀 Starting denoiser"
            if self.crossframe_mode_button.isChecked():
                log_message += " with CrossFrame"
            log_message += " using CPU"
                
            log_message += f": \"{denoise_exe}\""
            
            if self.crossframe_mode_button.isChecked():
                log_message += " -cf -f"
                
            log_message += f" -j \"{config_path}\""
            
            self.log_window.append_log(log_message)
            
            # Informations supplémentaires sur le mode utilisé et les optimisations
            self.log_window.append_log("ℹ️ CPU mode: Using all available CPU cores for denoising")
            self.log_window.append_log(f"⚡ Performance optimizations: Full image processing, high priority process, verbose output")
            
            # Afficher la commande complète pour debug
            command_str = " ".join([f'"{arg}"' if " " in arg else arg for arg in command])
            self.log_window.append_log(f"🔧 Full command: {command_str}")
            
            # Optimiser l'environnement système pour de meilleures performances
            env = os.environ.copy()
            
            # Variables d'environnement RenderMan pour optimiser les performances
            env['RMANTREE'] = renderman_path
            env['RMAN_THREADS'] = str(cpu_count)  # Utiliser tous les cœurs
            env['RMAN_DENOISE_THREADS'] = str(cpu_count)
            
            # Optimiser la mémoire pour RenderMan
            try:
                memory_gb = psutil.virtual_memory().available / (1024**3)
                # Allouer jusqu'à 75% de la RAM disponible pour RenderMan
                memory_mb = int(memory_gb * 0.75 * 1024)
                env['RMAN_MEMORY_LIMIT'] = str(memory_mb)
                self.log_window.append_log(f"💾 Allocated {memory_mb}MB RAM for RenderMan denoising")
            except:
                pass
            
            # Démarrer le processus avec priorité haute pour de meilleures performances
            if os.name == 'nt':  # Windows
                # Utiliser HIGH_PRIORITY_CLASS sur Windows
                import subprocess
                self.process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    bufsize=1,
                    env=env,
                    creationflags=subprocess.HIGH_PRIORITY_CLASS
                )
            else:  # Unix-like
                self.process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    bufsize=1,
                    env=env,
                    preexec_fn=lambda: os.nice(-10)  # Priorité haute
                )
            
            # Monitor denoiser output
            total_frames = len(frames)
            denoising_start_time = time.time()
            last_frame_time = None
            error_message = None
            
            # CPU mode - no GPU monitoring needed
            
            # Variables pour suivre les étapes du débruitage
            current_stage = ""
            aov_counters = {"albedo": 0, "diffuse": 0, "specular": 0, "subsurface": 0, "light_groups": 0}
            aov_totals = {"albedo": 0, "diffuse": 0, "specular": 0, "subsurface": 0, "light_groups": 0}
            
            # Ajouter un set pour éviter les doublons de logs
            processed_entries = set()
            
            # Calculer les totaux estimés pour chaque type d'AOV
            prefix = self.light_group_prefix.text().upper()
            for aov in selected_aovs:
                if "albedo" in aov.lower():
                    aov_totals["albedo"] += len(frames)
                elif "diffuse" in aov.lower():
                    if prefix in aov:
                        aov_totals["light_groups"] += len(frames)
                    else:
                        aov_totals["diffuse"] += len(frames)
                elif "specular" in aov.lower():
                    if prefix in aov:
                        aov_totals["light_groups"] += len(frames)
                    else:
                        aov_totals["specular"] += len(frames)
                elif "subsurface" in aov.lower():
                    aov_totals["subsurface"] += len(frames)
                else:
                    # Par défaut, considérer comme diffuse
                    aov_totals["diffuse"] += len(frames)
            
            for line in iter(self.process.stdout.readline, ''):
                line_text = line.strip()
                if line_text:
                    # Check for stop request
                    if self.stop_requested:
                        self.log_window.append_log("🛑 Stop requested during denoising. Terminating...")
                        try:
                            self.process.terminate()
                        except:
                            pass
                        return
                        
                    # Handle pause if requested
                    self.check_pause()
                    
                    # Check for error messages
                    if "ERROR" in line_text.upper():
                        error_message = line_text
                        self.log_window.append_log(line_text)
                        # Special error handling for missing AOVs
                        if "aov" in line_text.lower() and "not found" in line_text.lower():
                            missing_aov = line_text.split("'")[1] if "'" in line_text else "unknown"
                            QMessageBox.critical(self, "Missing AOV", 
                                                f"RenderMan denoiser error: AOV '{missing_aov}' not found.\n\n"
                                                f"Please check that all required AOVs are present in your EXR files.")
                
                    # Detect denoising stage changes
                    if "Processing albedo" in line_text:
                        current_stage = "albedo"
                        self.log_window.set_status("1: DENOISING RENDERMAN - ALBEDO")
                        self.log_window.append_log("\n🔄 Starting ALBEDO denoising")
                        # Mettre à jour la barre de progression globale
                        self.log_window.set_overall_progress(5)  # 5% quand commence l'étape albedo
                        # Forcer la mise à jour de l'interface
                        QApplication.processEvents()
                    elif "Processing diffuse" in line_text:
                        current_stage = "diffuse"
                        self.log_window.set_status("1: DENOISING RENDERMAN - ALBEDO / DIFFUSE")
                        self.log_window.append_log("\n🔄 Starting DIFFUSE denoising")
                        # Mettre à jour la barre de progression globale
                        self.log_window.set_overall_progress(global_phases["denoising_albedo"])  # 15% quand termine l'étape albedo
                        # Forcer la mise à jour de l'interface
                        QApplication.processEvents()
                    elif "Processing specular" in line_text:
                        current_stage = "specular"
                        self.log_window.set_status("1: DENOISING RENDERMAN - ALBEDO / DIFFUSE / SPECULAR")
                        self.log_window.append_log("\n🔄 Starting SPECULAR denoising")
                        # Mettre à jour la barre de progression globale
                        self.log_window.set_overall_progress(global_phases["denoising_diffuse"])  # 35% quand termine l'étape diffuse
                        # Forcer la mise à jour de l'interface
                        QApplication.processEvents()
                    elif "Processing subsurface" in line_text:
                        current_stage = "subsurface"
                        self.log_window.set_status("1: DENOISING RENDERMAN - ALBEDO / DIFFUSE / SUBSURFACE")
                        self.log_window.append_log("\n🔄 Starting SUBSURFACE denoising")
                        # Mettre à jour la barre de progression globale
                        self.log_window.set_overall_progress(global_phases["denoising_subsurface"])  # 25% quand commence l'étape subsurface
                        # Forcer la mise à jour de l'interface
                        QApplication.processEvents()
                
                    # Détecter les lignes indiquant l'application du débruitage à un fichier spécifique
                    if "Applying Denoiser:" in line_text:
                        # Afficher la ligne originale telle quelle
                        self.log_window.append_log(line_text)
                        
                        # Ne compter que si c'est un fichier de sortie dans temp_denoised (résultat final)
                        if "temp_denoised" in line_text and ">" in line_text:
                            # Extraire le nom du fichier et la couche (AOV)
                            parts = line_text.split("|")
                            if len(parts) >= 2:
                                # Extraire le fichier de sortie (après le >)
                                output_part = parts[0].strip()
                                layer_info = parts[1].strip()
                                layer_name = layer_info.split(":")[1].strip() if ":" in layer_info else "unknown"
                                
                                # Extraire le nom du fichier de sortie
                                if ">" in output_part:
                                    output_path = output_part.split(">")[1].strip()
                                    file_name = os.path.basename(output_path) if output_path else "unknown"
                                else:
                                    continue  # Pas un fichier de sortie, ignorer
                                
                                # Créer une clé unique pour éviter les doublons (fichier + layer)
                                unique_key = f"{file_name}|{layer_name}"
                                
                                # Vérifier si cette entrée a déjà été traitée
                                if unique_key in processed_entries:
                                    continue  # Ignorer les doublons
                                
                                # Ajouter à la liste des entrées traitées
                                processed_entries.add(unique_key)
                                
                                # Incrémenter le compteur approprié
                                if current_stage == "albedo" or "albedo" in layer_name.lower():
                                    aov_counters["albedo"] += 1
                                    progress_text = f"{aov_counters['albedo']}/{aov_totals['albedo']} albedo"
                                elif current_stage == "diffuse" or "diffuse" in layer_name.lower():
                                    # Vérifier si c'est un light group
                                    if prefix in layer_name:
                                        aov_counters["light_groups"] += 1
                                        progress_text = f"{aov_counters['diffuse']}/{aov_totals['diffuse']} diffuse, {aov_counters['light_groups']}/{aov_totals['light_groups']} light groups"
                                    else:
                                        aov_counters["diffuse"] += 1
                                        progress_text = f"{aov_counters['diffuse']}/{aov_totals['diffuse']} diffuse"
                                elif current_stage == "specular" or "specular" in layer_name.lower():
                                    # Vérifier si c'est un light group
                                    if prefix in layer_name:
                                        aov_counters["light_groups"] += 1
                                        progress_text = f"{aov_counters['specular']}/{aov_totals['specular']} specular, {aov_counters['light_groups']}/{aov_totals['light_groups']} light groups"
                                    else:
                                        aov_counters["specular"] += 1
                                        progress_text = f"{aov_counters['specular']}/{aov_totals['specular']} specular"
                                elif current_stage == "subsurface" or "subsurface" in layer_name.lower():
                                    aov_counters["subsurface"] += 1
                                    progress_text = f"{aov_counters['subsurface']}/{aov_totals['subsurface']} subsurface"
                                else:
                                    # Si on ne peut pas déterminer le type, ne pas compter
                                    continue
                                
                                # Afficher le progrès seulement après avoir compté
                                self.log_window.append_log(f"🔄 {progress_text}: {file_name} | layer: {layer_name}")
                                
                                # Calculer la progression globale
                                total_aovs = sum(aov_totals.values())
                                processed_aovs = sum(aov_counters.values())
                                
                                if total_aovs > 0:
                                    denoise_progress = phases["denoising"]["start"] + (
                                        (processed_aovs / total_aovs) * 
                                        (phases["denoising"]["end"] - phases["denoising"]["start"])
                                    )
                                    self.log_window.set_progress(int(denoise_progress))
                                
                                # Mettre à jour le statut avec l'étape actuelle et le progrès
                                stages_status = ""
                                if aov_counters["albedo"] > 0:
                                    stages_status += "ALBEDO"
                                if aov_counters["diffuse"] > 0:
                                    stages_status += " / DIFFUSE"
                                if aov_counters["subsurface"] > 0:
                                    stages_status += " / SUBSURFACE"    
                                if aov_counters["specular"] > 0:
                                    stages_status += " / SPECULAR"
                                if aov_counters["light_groups"] > 0:
                                    stages_status += " / LIGHT GROUPS"
                                    
                                # S'assurer qu'il y a au moins une étape affichée
                                if not stages_status:
                                    stages_status = current_stage.upper()
                                    
                                self.log_window.set_status(f"1: DENOISING RENDERMAN - {stages_status} - {progress_text}")
                                
                                # Calculer et mettre à jour le temps estimé
                                current_time = time.time()
                                if last_frame_time is not None and processed_aovs > 0:
                                    time_per_aov = (current_time - denoising_start_time) / processed_aovs
                                    remaining_aovs = total_aovs - processed_aovs
                                    
                                    # Calcul du temps restant pour le débruitage
                                    remaining_time = time_per_aov * remaining_aovs
                                    
                                    # Format time for display
                                    if remaining_time < 60:
                                        time_str = f"{int(remaining_time)} seconds"
                                    elif remaining_time < 3600:
                                        time_str = f"{int(remaining_time/60)} minutes {int(remaining_time%60)} seconds"
                                    else:
                                        time_str = f"{int(remaining_time/3600)} hours {int((remaining_time%3600)/60)} minutes"
                                    
                                    self.log_window.set_estimated_time(time_str)
                                
                                last_frame_time = current_time
                        else:
                            # Si le format ne correspond pas, afficher la ligne telle quelle
                            self.log_window.append_log(line_text)
                    else:
                        # Afficher les autres lignes sans modification
                        self.log_window.append_log(line_text)
                        
                        # Forcer la mise à jour de l'interface
                        QApplication.processEvents()
            
            self.process.wait()
            
            if self.stop_requested:
                self.log_window.append_log("🛑 Process stopped after denoising.")
                self.process = None
                return
                
            returncode = self.process.returncode
            self.process = None
            
            if returncode != 0:
                error_msg = error_message or f"RenderMan denoiser failed with code: {returncode}"
                QMessageBox.critical(self, "Denoiser Error", error_msg)
                raise Exception(error_msg)
            
            self.log_window.append_log("✅ Denoising completed")
            self.log_window.set_progress(phases["denoising"]["end"])
            self.log_window.set_overall_progress(global_phases["denoising_done"])  # 50% quand le débruitage est terminé
            
            # Forcer la mise à jour de l'interface
            QApplication.processEvents()
            
            # Handle pause if requested
            self.check_pause()
            
            # Phase: merging (30%)
            self.log_window.set_status("2: REBUILD BEAUTY - Merging AOVs...")
            self.log_window.append_log("\n🔄 2: REBUILD BEAUTY - Starting AOVs merging...")
            
            # Forcer la mise à jour de l'interface
            QApplication.processEvents()
            
            # Calculate actual denoise time
            actual_denoise_time = time.time() - denoising_start_time
            
            # Create a progress callback to update the main progress bar
            def merge_progress_callback(progress_percent):
                # Check for stop request
                if self.stop_requested:
                    return True  # Signal to stop processing
                    
                # Handle pause if requested
                self.check_pause()
                
                # Map 0-100% of merge to the merge phase range
                merge_range = phases["merging"]["end"] - phases["merging"]["start"]
                overall_progress = phases["merging"]["start"] + (progress_percent / 100 * merge_range)
                self.log_window.set_progress(int(overall_progress))
                
                # Mettre à jour la barre de progression globale (entre 50% et 75%)
                global_merge_progress = global_phases["denoising_done"] + (
                    (progress_percent / 100) * 
                    (global_phases["merging_done"] - global_phases["denoising_done"])
                )
                self.log_window.set_overall_progress(int(global_merge_progress))
                
                # Forcer la mise à jour de l'interface
                QApplication.processEvents()
                
                return False  # Signal to continue processing
            
            # Create a log callback that also updates the time estimate
            merge_start_time = time.time()
            def merge_log_callback(message):
                # Check for stop request
                if self.stop_requested:
                    return True  # Signal to stop processing
                    
                self.log_window.append_log(message)
                
                # Forcer la mise à jour de l'interface
                QApplication.processEvents()
                
                # Update time estimate if it's a progress update
                if "⏳ Progress:" in message:
                    elapsed_merge_time = time.time() - merge_start_time
                    if elapsed_merge_time > 0:
                        # Extract progress from message
                        parts = message.split()
                        if len(parts) >= 3:
                            progress_parts = parts[2].split('/')
                            if len(progress_parts) == 2:
                                try:
                                    current = int(progress_parts[0])
                                    total = int(progress_parts[1])
                                    if current > 0:
                                        percentage_done = current / total
                                        estimated_total_merge_time = elapsed_merge_time / percentage_done
                                        remaining_merge_time = estimated_total_merge_time - elapsed_merge_time
                                        
                                        # Update integrator estimate
                                        if self.enable_integrator_checkbox.isChecked():
                                            integrator_estimate = (estimated_total_merge_time / total_frames) * total_frames * 0.7
                                            remaining_total = remaining_merge_time + integrator_estimate
                                        else:
                                            remaining_total = remaining_merge_time
                                        
                                        # Format time for display
                                        if remaining_total < 60:
                                            time_str = f"{int(remaining_total)} seconds"
                                        elif remaining_total < 3600:
                                            time_str = f"{int(remaining_total/60)} minutes {int(remaining_total%60)} seconds"
                                        else:
                                            time_str = f"{int(remaining_total/3600)} hours {int((remaining_total%3600)/60)} minutes"
                                        
                                        self.log_window.set_estimated_time(time_str)
                                except:
                                    pass
                return False  # Signal to continue processing

            merge_final_exrs(
                output_folder=beauty_dir,
                frame_list=frames,
                input_folder=input_path,
                selected_aovs=selected_aovs,
                compression_mode=self.selected_compression,
                compression_level=self.compression_level if self.selected_compression in ["DWAA", "DWAB"] else None,
                log_callback=merge_log_callback,
                progress_callback=merge_progress_callback,
                temp_folder=temp_dir,
                shadow_mode=self.shadow_mode,
                shadow_aovs=self.get_checked_shadow_aovs() if self.shadow_mode else [],
                stop_check=lambda: self.stop_requested,
                use_gpu=False
            )
            
            if self.stop_requested:
                self.log_window.append_log("🛑 Process stopped after merging.")
                return
                
            # Handle pause if requested
            self.check_pause()
            
            # If integrator is disabled, skip to cleanup
            if not self.integrator_mode_button.isChecked():
                self.log_window.set_progress(100)
                self.log_window.set_overall_progress(100)  # 100% quand tout est terminé sans intégrateur
            else:
                self.log_window.set_progress(phases["merging"]["end"])
                self.log_window.set_overall_progress(global_phases["merging_done"])  # 75% quand la fusion est terminée
                
                # Phase: integrators (15%)
                self.log_window.set_status("3: REBUILD INTEGRATOR - Separating integrators...")
                self.log_window.append_log("\n🔄 3: REBUILD INTEGRATOR - Starting integrator separation...")
                
                # Forcer la mise à jour de l'interface
                QApplication.processEvents()
                
                # Create a progress callback for integrator phase
                def integrator_progress_callback(progress_percent):
                    # Check for stop request
                    if self.stop_requested:
                        return True  # Signal to stop processing
                        
                    # Handle pause if requested
                    self.check_pause()
                    
                    # Map 0-100% of integrator to the integrator phase range
                    integrator_range = phases["integrators"]["end"] - phases["integrators"]["start"]
                    overall_progress = phases["integrators"]["start"] + (progress_percent / 100 * integrator_range)
                    self.log_window.set_progress(int(overall_progress))
                    
                    # Mettre à jour la barre de progression globale (entre 75% et 100%)
                    global_integrator_progress = global_phases["merging_done"] + (
                        (progress_percent / 100) * 
                        (global_phases["integrators_done"] - global_phases["merging_done"])
                    )
                    self.log_window.set_overall_progress(int(global_integrator_progress))
                    
                    # Forcer la mise à jour de l'interface
                    QApplication.processEvents()
                    
                    return False  # Signal to continue processing
                
                # Create a log callback that also updates the time estimate
                integrator_start_time = time.time()
                def integrator_log_callback(message):
                    # Check for stop request
                    if self.stop_requested:
                        return True  # Signal to stop processing
                        
                    self.log_window.append_log(message)
                    
                    # Forcer la mise à jour de l'interface
                    QApplication.processEvents()
                    
                    # Update time estimate if it's a progress update
                    if "⏳ Progress:" in message:
                        elapsed_integrator_time = time.time() - integrator_start_time
                        if elapsed_integrator_time > 0:
                            # Extract progress from message
                            parts = message.split()
                            if len(parts) >= 3:
                                progress_parts = parts[2].split('/')
                                if len(progress_parts) == 2:
                                    try:
                                        current = int(progress_parts[0])
                                        total = int(progress_parts[1])
                                        if current > 0:
                                            percentage_done = current / total
                                            estimated_total_integrator_time = elapsed_integrator_time / percentage_done
                                            remaining_integrator_time = estimated_total_integrator_time - elapsed_integrator_time
                                            
                                            # Format time for display
                                            if remaining_integrator_time < 60:
                                                time_str = f"{int(remaining_integrator_time)} seconds"
                                            elif remaining_integrator_time < 3600:
                                                time_str = f"{int(remaining_integrator_time/60)} minutes {int(remaining_integrator_time%60)} seconds"
                                            else:
                                                time_str = f"{int(remaining_integrator_time/3600)} hours {int((remaining_integrator_time%3600)/60)} minutes"
                                            
                                            self.log_window.set_estimated_time(time_str)
                                    except:
                                        pass
                    return False  # Signal to continue processing
                
                selected_integrators = self.get_checked_integrators()
                run_integrator_generate(
                    input_folder=input_path,
                    output_folder=integrator_dir,  # Use INTEGRATOR subdirectory
                    selected_integrators=selected_integrators,
                    compression_mode=self.selected_compression,
                    compression_level=self.compression_level if self.selected_compression in ["DWAA", "DWAB"] else None,
                    log_callback=integrator_log_callback,
                    progress_callback=integrator_progress_callback,
                    stop_check=lambda: self.stop_requested,
                    use_gpu=False
                )
                
                if self.stop_requested:
                    self.log_window.append_log("🛑 Process stopped after integrator generation.")
                    return
                
                self.log_window.set_progress(100)
                self.log_window.set_overall_progress(100)  # 100% quand tout est terminé
            
            # Cleanup: Delete temp_denoised folder
            self.log_window.append_log("🧹 Cleaning up temporary files...")
            try:
                import shutil
                shutil.rmtree(temp_dir)
                self.log_window.append_log(f"✅ Removed temporary directory: {temp_dir}")
            except Exception as e:
                self.log_window.append_log(f"⚠️ Warning: Could not remove temporary directory: {str(e)}")
            
            # Calculate actual total time
            total_process_time = time.time() - denoising_start_time
            if total_process_time < 60:
                total_time_str = f"{int(total_process_time)} seconds"
            elif total_process_time < 3600:
                total_time_str = f"{int(total_process_time/60)} minutes {int(total_process_time%60)} seconds"
            else:
                total_time_str = f"{int(total_process_time/3600)} hours {int((total_process_time%3600)/60)} minutes"
                
            self.log_window.set_status(f"Process completed in {total_time_str}")
            self.log_window.append_log(f"✅ Process completed in {total_time_str}!")
            
            # Forcer la mise à jour de l'interface
            QApplication.processEvents()
            
            # Si nous sommes en mode batch, notifier le parent que le traitement est terminé
            if batch_mode and hasattr(self, 'batch_finished_callback') and hasattr(self, 'batch_tab_index'):
                # Vérifier si le traitement s'est terminé avec succès (sans stop_requested)
                success = not self.stop_requested
                self.batch_finished_callback(self.batch_tab_index, success)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            self.log_window.append_log(f"Error: {str(e)}")
        finally:
            self.process = None
            self.set_processing_state(False)
            
    def check_pause(self):
        """Check if process should be paused and wait if needed"""
        while self.pause_requested and not self.stop_requested:
            # Keep UI responsive while paused
            QApplication.processEvents()
            time.sleep(0.1)  # Small sleep to avoid high CPU usage

    def set_processing_state(self, is_processing):
        """Update UI state during processing"""
        self.processing = is_processing
        
        # Mettre à jour l'état des widgets
        for widget in self.findChildren(QPushButton):
            if widget is not self.emergency_stop_btn:  # Do not disable the emergency stop button
                widget.setEnabled(not is_processing)
        
        # Show emergency stop button when processing
        if is_processing:
            # Afficher le bouton dans son conteneur dédié
            self.emergency_stop_btn.setVisible(True)
            self.emergency_container.setVisible(True)
            
            # Start timer that periodically checks process state
            if not self.process_check_timer:
                self.process_check_timer = QTimer()
                self.process_check_timer.timeout.connect(self.check_process_state)
                self.process_check_timer.start(500)  # Vérifier toutes les 500ms
        else:
            # Hide emergency button and stop timer
            self.emergency_stop_btn.setVisible(False)
            self.emergency_container.setVisible(False)
            if self.process_check_timer:
                self.process_check_timer.stop()
                self.process_check_timer = None
            
        for widget in self.findChildren(QLineEdit):
            widget.setEnabled(not is_processing)
            
        for widget in self.findChildren(QListWidget):
            widget.setEnabled(not is_processing)
            
        # Ne plus cacher la fenêtre de log à la fin du traitement
        if not is_processing:
            # Mettre à jour le titre de la fenêtre de log pour indiquer que le traitement est terminé
            self.log_window.setWindowTitle("DenoiZer - Processing Complete")
            # Laisser la fenêtre ouverte
        else:
            # Mettre à jour le titre de la fenêtre de log pour indiquer que le traitement est en cours
            self.log_window.setWindowTitle("DenoiZer - Processing")
            
        # Forcer une mise à jour complète de l'interface
        QApplication.processEvents()
        
    def check_process_state(self):
        """Periodically check process state and update the interface"""
        # If the process is stopped, update the interface
        if self.processing and self.process is None:
            # Forcer l'actualisation de l'interface
            QApplication.processEvents()
            
        # Si un sous-processus existe, vérifier s'il est toujours en cours
        if self.process and hasattr(self.process, 'poll'):
            returncode = self.process.poll()
            if returncode is not None:  # Le processus est terminé
                # Afficher le résultat dans les logs si ce n'est pas déjà fait
                if returncode != 0:
                    self.log_window.append_log(f"⚠️ Process terminated with error code: {returncode}")
                # Mettre à jour l'interface uniquement si nous sommes encore en état de traitement
                if self.processing:
                    self.set_processing_state(False)

    # Method to validate and normalize paths
    def validate_paths(self):
        input_path = self.input_path.text()
        output_path = self.output_path.text()
        
        if not input_path or not os.path.isdir(input_path):
            self.log_window.append_log("❌ Input folder does not exist or is not valid.")
            return False
            
        if not output_path or not os.path.isdir(output_path):
            self.log_window.append_log("❌ Output folder does not exist or is not valid.")
            return False
            
        # Normalize paths to avoid separator issues
        input_path = os.path.normpath(input_path)
        output_path = os.path.normpath(output_path)
        
        self.log_window.append_log(f"✅ Input path validated: {input_path}")
        self.log_window.append_log(f"✅ Output path validated: {output_path}")
        
        return True

    def scan_renderman_versions(self):
        """Scan for available RenderMan versions"""
        base_path = "C:/Program Files/Pixar"
        if os.path.exists(base_path):
            versions = sorted([
                d for d in os.listdir(base_path)
                if d.startswith("RenderManProServer")
            ], reverse=True)
            
            if versions:
                latest_version = os.path.join(base_path, versions[0])
                if not self.config.get("RENDERMAN_PROSERVER"):
                    self.config["RENDERMAN_PROSERVER"] = latest_version
                    self.save_config()
                self.renderman_path.setText(self.config["RENDERMAN_PROSERVER"])
                
    def change_renderman_version(self):
        """Allow user to change RenderMan version"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select RenderMan Pro Server Directory",
            "C:/Program Files/Pixar"
        )
        if folder and "RenderManProServer" in folder:
            self.config["RENDERMAN_PROSERVER"] = folder
            self.save_config()
            self.renderman_path.setText(folder)
        elif folder:
            QMessageBox.warning(
                self,
                "Invalid Selection",
                "Please select a valid RenderMan Pro Server directory"
            )
            
    def save_config(self):
        """Save configuration to user_config.json"""
        # Sauvegarder l'état du bouton CrossFrame
        self.config["ENABLE_CROSSFRAME"] = self.crossframe_mode_button.isChecked()
        # Sauvegarder l'état de la case à cocher GPU si elle existe (obsolète mais maintenu pour compatibilité)
        if hasattr(self, 'use_gpu_checkbox'):
            self.config["USE_GPU"] = self.use_gpu_checkbox.isChecked()
        # Sauvegarder l'état de la case à cocher GPU pour le traitement d'images
        if hasattr(self, 'use_gpu_processing_checkbox'):
            self.config["USE_GPU_PROCESSING"] = self.use_gpu_processing_checkbox.isChecked()
        
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_config.json")
        with open(config_path, "w") as f:
            json.dump(self.config, f, indent=2)
            

            
    def show_log_window(self):
        """Show the log window and bring it to front"""
        self.log_window.show()
        self.log_window.raise_()
        self.log_window.activateWindow()

    def toggle_integrator_mode(self):
        """Toggle Integrator mode"""
        integrator_enabled = self.integrator_mode_button.isChecked()
        
        if integrator_enabled:
            self.integrator_mode_button.setText("INTEGRATOR EXR")
            self.log_window.append_log("✅ Build Integrator enabled")
        else:
            self.integrator_mode_button.setText("INTEGRATOR EXR")
            self.log_window.append_log("❌ Build Integrator disabled")
        
        # Afficher/masquer la section intégrateur
        self.integrator_section.setVisible(integrator_enabled)
        self.build_integrator_action.setVisible(integrator_enabled)  # Afficher/masquer l'action dans le menu
        
        # Si le mode actuel est BUILD INTEGRATOR et qu'on désactive l'intégrateur, revenir à DENOIZE
        if not integrator_enabled and self.current_button_mode == "BUILD INTEGRATOR":
            self.change_button_mode("DENOIZE")
        
        # Sauvegarder dans la configuration
        self.config["ENABLE_INTEGRATOR"] = integrator_enabled
        self.save_config()
        
        # Forcer la mise à jour de l'interface
        QApplication.processEvents()

    def toggle_integrator_separator(self):
        """Active/désactive la section séparation d'intégrateur (legacy function)"""
        # Rediriger vers la nouvelle fonction
        self.toggle_integrator_mode()

    def check_disk_space(self, path, required_mb=2000):
        """Check if there's enough disk space in the specified path"""
        try:
            import shutil
            total, used, free = shutil.disk_usage(path)
            free_mb = free / (1024 * 1024)  # Convert bytes to MB
            
            if free_mb < required_mb:
                return False, f"Only {int(free_mb)} MB free on disk. At least {required_mb} MB recommended."
            return True, f"Disk space OK: {int(free_mb)} MB free"
        except Exception as e:
            return False, f"Error checking disk space: {str(e)}"

    def validate_renderman(self):
        """Validate that RenderMan is available and installed correctly"""
        renderman_path = self.config.get("RENDERMAN_PROSERVER", "")
        
        # Check if path exists
        if not renderman_path or not os.path.exists(renderman_path):
            QMessageBox.critical(self, "RenderMan Not Found", 
                                "RenderMan Pro Server path not found or invalid.\n"
                                "Please specify a valid RenderMan installation path.")
            return False
        
        # Check for denoise_batch.exe
        denoise_exe = os.path.join(renderman_path, "bin", "denoise_batch.exe")
        if not os.path.exists(denoise_exe):
            QMessageBox.critical(self, "RenderMan Denoiser Not Found", 
                                f"Could not find denoiser at:\n{denoise_exe}\n"
                                "Please check your RenderMan installation.")
            return False
        
        # Check for required parameter files (both CrossFrame and standard)
        # Fichiers pour CrossFrame
        param_file_cf = os.path.join(renderman_path, "lib", "denoise", "20970-renderman.param")
        topo_file_cf = os.path.join(renderman_path, "lib", "denoise", "full_w7_4sv2_sym_gen2.topo")
        
        # Fichiers standard
        param_file_std = os.path.join(renderman_path, "lib", "denoise", "20973-renderman.param")
        topo_file_std = os.path.join(renderman_path, "lib", "denoise", "full_w1_5s_sym_gen2.topo")
        
        missing_files = []
        if not os.path.exists(param_file_cf):
            missing_files.append("20970-renderman.param (CrossFrame)")
        if not os.path.exists(topo_file_cf):
            missing_files.append("full_w7_4sv2_sym_gen2.topo (CrossFrame)")
        if not os.path.exists(param_file_std):
            missing_files.append("20973-renderman.param (Standard)")
        if not os.path.exists(topo_file_std):
            missing_files.append("full_w1_5s_sym_gen2.topo (Standard)")
        
        if missing_files:
            QMessageBox.critical(self, "RenderMan Parameter Files Missing", 
                                f"Required parameter files for denoising are missing:\n" +
                                "\n".join(f"• {file}" for file in missing_files) +
                                "\n\nPlease check your RenderMan installation.")
            return False
        
        return True

    def validate_aovs(self, input_path, selected_aovs):
        """Validate that required AOVs are present in the input files"""
        # Get a sample EXR file
        files = sorted([f for f in os.listdir(input_path) if f.endswith(".exr")])
        if not files:
            QMessageBox.critical(self, "No EXR Files", 
                                f"No .exr files found in input folder:\n{input_path}")
            return False
        
        # Open the file and check channels
        first_file = os.path.join(input_path, files[0])
        try:
            inp = oiio.ImageInput.open(first_file)
            if not inp:
                QMessageBox.critical(self, "Error Opening EXR", 
                                    f"Could not open file:\n{first_file}")
                return False
            
            available_channels = inp.spec().channelnames
            inp.close()
            
            # Note: We're skipping RGBA validation since the app works fine without these channels
            
            # Check for selected AOVs
            found_aovs = []
            missing_aovs = []
            
            for aov in selected_aovs:
                # Check if AOV exists directly
                if aov in available_channels:
                    found_aovs.append(aov)
                else:
                    # Check if AOV has component channels
                    aov_channels = [ch for ch in available_channels if ch.startswith(f"{aov}.")]
                    if aov_channels:
                        found_aovs.append(aov)
                    else:
                        missing_aovs.append(aov)
            
            if missing_aovs:
                result = QMessageBox.warning(self, "Missing AOVs", 
                                        f"The following selected AOVs are missing from input files:\n"
                                        f"{', '.join(missing_aovs)}\n\n"
                                        f"Continue anyway?",
                                        QMessageBox.Yes | QMessageBox.No)
                return result == QMessageBox.Yes
            
            return True
        
        except Exception as e:
            QMessageBox.critical(self, "Error Validating AOVs", 
                                f"Error checking AOVs in file:\n{first_file}\n\n{str(e)}")
            return False

    def update_aov_lists_after_light_group_change(self):
        """Actualise les listes Beauty et Integrator après un changement dans les tableaux diffuse et specular"""
        # Créer une liste des AOVs dans les light groups
        light_group_aovs = []
        for i in range(self.diffuse_aovs.count()):
            light_group_aovs.append(self.diffuse_aovs.item(i).text())
        for i in range(self.specular_aovs.count()):
            light_group_aovs.append(self.specular_aovs.item(i).text())
            
        # Récupérer l'état actuel de la case à cocher pour les AOVs denoise
        show_denoise = self.show_denoise_checkbox.isChecked()
        
        # Liste des mots-clés qui identifient les Denoise AOVs
        denoise_keywords = [
            "mse", "samplecount", "var", "variance",
            "forward", "backward", "forwards", "zfiltered",
            "normal_mse", "normal_var",
            "diffuse_mse", "specular_mse", "albedo_mse", "albedo_var"
        ]
            
        # Parcourir la liste Beauty et masquer les AOVs qui sont dans les light groups
        for i in range(self.aov_list.count()):
            item = self.aov_list.item(i)
            widget = self.aov_list.itemWidget(item)
            if widget:
                label = widget.findChild(QLabel)
                aov_text = label.text()
                aov_lower = aov_text.lower()
                
                # Vérifier si c'est un AOV denoise
                is_denoise = any(keyword in aov_lower for keyword in denoise_keywords)
                
                # Déterminer si l'élément doit être masqué:
                # - Masquer si c'est dans les light groups
                # - OU si c'est un AOV denoise et que show_denoise est False
                should_hide = aov_text in light_group_aovs or (is_denoise and not show_denoise)
                
                # Appliquer la visibilité
                item.setHidden(should_hide)
        
        # Même chose pour la liste Integrator
        for i in range(self.integrator_list.count()):
            item = self.integrator_list.item(i)
            widget = self.integrator_list.itemWidget(item)
            if widget:
                label = widget.findChild(QLabel)
                aov_text = label.text()
                aov_lower = aov_text.lower()
                
                # Vérifier si c'est un AOV denoise
                is_denoise = any(keyword in aov_lower for keyword in denoise_keywords)
                
                # Déterminer si l'élément doit être masqué:
                should_hide = aov_text in light_group_aovs or (is_denoise and not show_denoise)
                
                # Appliquer la visibilité
                item.setHidden(should_hide)
                
        # Message de log pour confirmer l'actualisation
        self.log_window.append_log("ℹ️ Beauty and Integrator lists updated")

    def toggle_crossframe_mode(self):
        """Toggle CrossFrame mode"""
        crossframe_enabled = self.crossframe_mode_button.isChecked()
        
        if crossframe_enabled:
            self.crossframe_mode_button.setText("CROSS FRAME")
            self.log_window.append_log("✅ CrossFrame Mode enabled - Better temporal coherence between frames")
        else:
            self.crossframe_mode_button.setText("SINGLE FRAME")
            self.log_window.append_log("✅ Single Frame Mode enabled - Each frame processed independently")
        
        # Sauvegarder dans la configuration
        self.config["ENABLE_CROSSFRAME"] = crossframe_enabled
        self.save_config()
        
        # Forcer la mise à jour de l'interface
        QApplication.processEvents()

    def toggle_shadow_mode(self):
        """Toggle shadow mode"""
        self.shadow_mode = self.shadow_mode_button.isChecked()
        
        if self.shadow_mode:
            self.shadow_mode_button.setText("SHADOW MODE")
            # Cacher les sections non nécessaires en mode shadow
            self.light_groups_section.setVisible(False)
            self.aovs_section.setVisible(False)
            # Cacher aussi les options liées à l'intégrateur
            # Trouver le label "Enable Build Integrator:"
            for i in range(self.dirs_section.content_layout.count()):
                item = self.dirs_section.content_layout.itemAt(i)
                if isinstance(item, QHBoxLayout):
                    first_widget = item.itemAt(0).widget() if item.count() > 0 else None
                    if isinstance(first_widget, QLabel) and first_widget.text() == "Enable Build Integrator:":
                        # Hide all widgets in this layout
                        for j in range(item.count()):
                            widget = item.itemAt(j).widget()
                            if widget:
                                widget.setVisible(False)
                        break
            # Supprimer la référence à integrator_btn qui n'existe pas
            # self.integrator_btn.setVisible(False)  # Cette ligne cause l'erreur
            self.integrator_section.setVisible(False)
            # Afficher uniquement la section Shadows Configuration
            self.shadows_section.setVisible(True)
            # Activer automatiquement les shadows dans la configuration
            self.config["ENABLE_SHADOWS"] = True
            self.save_config()
            self.log_window.append_log("✅ Shadow Mode enabled - Only shadows will be processed")
            self.log_window.append_log("ℹ️ Shadow Configuration section is now visible")
        else:
            self.shadow_mode_button.setText("SHADOW MODE")
            # Restaurer l'affichage normal
            self.light_groups_section.setVisible(True)
            self.aovs_section.setVisible(True)
            # Restaurer les options liées à l'intégrateur
            # Trouver le label "Enable Build Integrator:"
            for i in range(self.dirs_section.content_layout.count()):
                item = self.dirs_section.content_layout.itemAt(i)
                if isinstance(item, QHBoxLayout):
                    first_widget = item.itemAt(0).widget() if item.count() > 0 else None
                    if isinstance(first_widget, QLabel) and first_widget.text() == "Enable Build Integrator:":
                        # Show all widgets in this layout
                        for j in range(item.count()):
                            widget = item.itemAt(j).widget()
                            if widget:
                                widget.setVisible(True)
                        break
            # Supprimer aussi cette référence
            # self.integrator_btn.setVisible(self.integrator_mode_button.isChecked())
            self.integrator_section.setVisible(self.integrator_mode_button.isChecked())
            # Cacher la section Shadows Configuration
            self.shadows_section.setVisible(False)
            # Désactiver les shadows dans la configuration
            self.config["ENABLE_SHADOWS"] = False
            self.save_config()
            self.log_window.append_log("✅ Normal Mode enabled - All AOVs will be processed")
            
        # Forcer la mise à jour de l'interface
        QApplication.processEvents()

    def get_checked_shadow_aovs(self):
        """Get checked AOVs from the Shadow Configuration list"""
        return self.get_checked_items(self.shadows_aov_list)

    def process_stop_requested(self):
        """Handle stop request from log window"""
        self.stop_requested = True
        self.log_window.append_log("🛑 Process will terminate after current operation")
        
        # Terminate the process if it exists
        if self.process and hasattr(self.process, 'poll') and self.process.poll() is None:
            try:
                import psutil
                import signal
                import os
                
                # On Windows, use taskkill to force stop
                if os.name == 'nt':
                    try:
                        if self.process.pid:
                            os.system(f'taskkill /F /PID {self.process.pid}')
                            self.log_window.append_log(f"🛑 Forced stop via taskkill for PID {self.process.pid}")
                    except Exception as e:
                        self.log_window.append_log(f"⚠️ Error during taskkill stop: {e}")
                        
                    # Specific search for denoise_batch to stop it
                    try:
                        # Trouver les processus 'denoise_batch.exe' qui pourraient être en cours
                        current_process = psutil.Process()
                        all_processes = current_process.children(recursive=True)
                        denoise_processes = [p for p in all_processes if 'denoise_batch' in p.name().lower()]
                        
                        if denoise_processes:
                            for proc in denoise_processes:
                                try:
                                    self.log_window.append_log(f"🛑 Forced stop of RenderMan process: {proc.pid}")
                                    os.system(f'taskkill /F /PID {proc.pid}')
                                except Exception as e:
                                    self.log_window.append_log(f"⚠️ Error stopping RenderMan process: {e}")
                    except Exception as e:
                        self.log_window.append_log(f"⚠️ Error finding RenderMan processes: {e}")
                        
                # Try to get process ID and children via psutil
                try:
                    parent = psutil.Process(self.process.pid)
                    # Kill child processes first
                    children = parent.children(recursive=True)
                    for child in children:
                        try:
                            # Use SIGTERM for a cleaner stop
                            child.send_signal(signal.SIGTERM)
                            self.log_window.append_log(f"🛑 Sending SIGTERM signal to child process {child.pid}")
                        except:
                            # Force stop if SIGTERM doesn't work
                            try:
                                child.kill()
                                self.log_window.append_log(f"🛑 Forced stop of child process {child.pid}")
                            except:
                                pass
                    
                    # Then kill the parent process
                    parent.send_signal(signal.SIGTERM)
                    self.log_window.append_log(f"🛑 Sending SIGTERM signal to main process {parent.pid}")
                    
                    # Wait a moment to let the process terminate cleanly
                    import time
                    time.sleep(0.5)
                    
                    # If the process is still alive, kill it forcefully
                    if parent.is_running():
                        parent.kill()
                        self.log_window.append_log(f"🛑 Forced stop of main process {parent.pid}")
                except:
                    # Fallback if psutil fails: essayer avec os.kill
                    try:
                        import os
                        os.kill(self.process.pid, signal.SIGTERM)
                        self.log_window.append_log(f"🛑 Sending SIGTERM signal to PID {self.process.pid}")
                        time.sleep(0.5)
                        
                        # Check if the process is still alive
                        if self.process.poll() is None:
                            os.kill(self.process.pid, signal.SIGKILL)
                            self.log_window.append_log(f"🛑 Sending SIGKILL signal to PID {self.process.pid}")
                    except:
                        # Last method: subprocess.terminate()
                        self.log_window.append_log("🛑 Attempting to stop via subprocess.terminate()")
                        self.process.terminate()
            except:
                # Vraiment la dernière méthode
                try:
                    self.process.kill()
                    self.log_window.append_log("🛑 Process terminated with kill()")
                except:
                    self.log_window.append_log("⚠️ Failed to terminate process - trying standard method")
                    try:
                        self.process.terminate()
                        self.log_window.append_log("🛑 Process terminated with terminate()")
                    except:
                        self.log_window.append_log("⚠️ Failed to terminate process completely")
        
        # Reset process reference
        self.process = None
        
        # Set UI state to not processing
        self.set_processing_state(False)
        self.log_window.append_log("⚠️ Process stopped by user")
        self.log_window.set_status("Process stopped by user")
        
    def emergency_stop(self):
        """Handle emergency stop request - force kill the process"""
        self.stop_requested = True
        self.log_window.append_log("🛑 EMERGENCY STOP REQUESTED")
        
        # Try to stop the process more aggressively
        emergency_successful = False
        
        if self.process:
            try:
                import psutil
                import signal
                import os
                
                # Get all child processes of the current process
                try:
                    # Trouver les processus 'denoise_batch.exe' qui pourraient être en cours
                    current_process = psutil.Process()
                    all_processes = current_process.children(recursive=True)
                    denoise_processes = [p for p in all_processes if 'denoise_batch' in p.name().lower()]
                    
                    if denoise_processes:
                        for proc in denoise_processes:
                            try:
                                self.log_window.append_log(f"🛑 Forced stop of RenderMan process: {proc.pid}")
                                proc.kill()
                                emergency_successful = True
                            except:
                                pass
                except:
                    pass
                
                # Essayer de tuer directement notre processus
                if self.process.pid:
                    try:
                        # On Windows, use taskkill to force stop
                        if os.name == 'nt':
                            os.system(f'taskkill /F /PID {self.process.pid}')
                            self.log_window.append_log(f"🛑 Forced stop via taskkill for PID {self.process.pid}")
                        else:
                            # Sous UNIX, utiliser SIGKILL
                            os.kill(self.process.pid, signal.SIGKILL)
                            self.log_window.append_log(f"🛑 Forced stop via SIGKILL for PID {self.process.pid}")
                        emergency_successful = True
                    except:
                        pass
            except:
                pass
                
            # Dernière chance: essayer le terminate() classique
            if not emergency_successful:
                try:
                    self.process.kill()
                    self.log_window.append_log("🛑 Process terminated with kill()")
                    emergency_successful = True
                except:
                    try:
                        self.process.terminate()
                        self.log_window.append_log("🛑 Process terminated with terminate()")
                        emergency_successful = True
                    except:
                        self.log_window.append_log("⚠️ Failed to terminate process - it will finish normally")
        
        # Reset the interface even if the process could not be stopped
        self.process = None
        self.set_processing_state(False)
        
        if emergency_successful:
            self.log_window.append_log("✅ Emergency stop successful - application reset")
        else:
            self.log_window.append_log("⚠️ Emergency stop attempted - UI reset but process may still be running")
            
        # Specific message for users in case of failure
        if not emergency_successful:
            QMessageBox.warning(self, "Emergency Stop", 
                              "The UI has been reset, but the RenderMan process may still be running in the background.\n\n"
                              "If you want to completely stop it, you may need to end the process manually using Task Manager.")
            
        self.log_window.set_status("Emergency Stop Executed")

    def eventFilter(self, obj, event):
        """Filter for keyboard events to capture Escape key"""
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QKeyEvent
        
        if event.type() == QEvent.KeyPress:
            key_event = event
            # Capturer la touche Échap
            if key_event.key() == Qt.Key_Escape and self.processing:
                self.emergency_stop()
                return True
        return super().eventFilter(obj, event)

    def change_button_mode(self, mode):
        """Change le mode du bouton principal et son texte"""
        self.current_button_mode = mode
        self.run_btn.setText(mode)
        
        # Style de base avec police Cute Pixel et texte encore plus agrandi
        # Chercher la fenêtre principale qui contient loaded_font_family
        main_window = self
        while main_window.parent() and not hasattr(main_window, 'loaded_font_family'):
            main_window = main_window.parent()
        
        font_family = getattr(main_window, 'loaded_font_family', 'Courier New')
        base_style = f"""
            QPushButton {{
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px;
                font-family: '{font_family}', 'Courier New', monospace;
                font-size: 64px;
                font-weight: bold;
                text-align: center;
            }}
            QPushButton:pressed {{
                background-color: rgba(255, 255, 255, 0.1);
            }}
            QPushButton:disabled {{
                background-color: #444444;
                color: #999999;
            }}
        """
        
        # Ajuster le style du bouton en fonction du mode
        if mode == "DENOIZE":
            # Style bleu pour DENOIZE
            button_color = "#0078d7"  # Bleu Microsoft
            hover_color = "#0086f0"
            pressed_color = "#005fa3"
        elif mode == "BUILD BEAUTY":
            # Orange
            button_color = "#d17a22"
            hover_color = "#e08a32"
            pressed_color = "#c16a12"
        elif mode == "BUILD INTEGRATOR":
            # Vert
            button_color = "#5d8a2a"
            hover_color = "#6d9a3a"
            pressed_color = "#4d7a1a"
        
        # Appliquer le style complet
        full_style = base_style.replace("QPushButton {", f"""
            QPushButton {{
                background-color: {button_color};
        """) + f"""
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:pressed {{
                background-color: {pressed_color};
            }}
        """
        
        self.run_btn.setStyleSheet(full_style)
        
        # Style pour le bouton menu
        self.run_menu_btn.setStyleSheet(f"""
            QToolButton {{
                border-left: none;
                background-color: {button_color};
                padding: 0 5px;
                font-family: '{font_family}', 'Courier New', monospace;
            }}
            QToolButton:hover {{
                background-color: {hover_color};
            }}
        """)
        
        # Mettre à jour l'info dans le log
        self.log_window.append_log(f"✅ Button mode changed to {mode}")

    def run_button_action(self):
        """Exécute l'action appropriée en fonction du mode actuel du bouton"""
        if self.current_button_mode == "DENOIZE":
            self.run_denoise()

        elif self.current_button_mode == "BUILD BEAUTY":
            self.run_only_merge()
        elif self.current_button_mode == "BUILD INTEGRATOR":
            self.run_only_integrator()
            
        
    def create_denoise_config(self, frames, use_gpu=None):
        """Crée la configuration JSON pour le débruitage avec les paramètres spécifiés"""
        input_path = self.input_path.text()
        output_path = self.output_path.text()
        temp_dir = os.path.join(output_path, "temp_denoised")
        os.makedirs(temp_dir, exist_ok=True)
        
        # Créer les dossiers aux nécessaires
        aux_albedo_dir = os.path.join(temp_dir, "aux-albedo")
        aux_diffuse_dir = os.path.join(temp_dir, "aux-diffuse")
        aux_specular_dir = os.path.join(temp_dir, "aux-specular")
        aux_subsurface_dir = os.path.join(temp_dir, "aux-subsurface")
        
        os.makedirs(aux_albedo_dir, exist_ok=True)
        os.makedirs(aux_diffuse_dir, exist_ok=True)
        os.makedirs(aux_specular_dir, exist_ok=True)
        os.makedirs(aux_subsurface_dir, exist_ok=True)
        
        # Choisir les fichiers de paramètres selon l'état du CrossFrame
        renderman_path = self.config.get("RENDERMAN_PROSERVER")
        if self.crossframe_mode_button.isChecked():
            # CrossFrame activé : utiliser les paramètres optimisés pour le débruitage temporel
            param = os.path.join(renderman_path, "lib", "denoise", "20970-renderman.param").replace("\\", "/")
            topo = os.path.join(renderman_path, "lib", "denoise", "full_w7_4sv2_sym_gen2.topo").replace("\\", "/")
        else:
            # CrossFrame désactivé : utiliser les paramètres standard
            param = os.path.join(renderman_path, "lib", "denoise", "20973-renderman.param").replace("\\", "/")
            topo = os.path.join(renderman_path, "lib", "denoise", "full_w1_5s_sym_gen2.topo").replace("\\", "/")
            
        # Lister les AOVs sélectionnés
        selected_aovs = self.get_checked_aovs()
        light_groups_config = self.get_light_groups_config()
        
        # Gérer l'option GPU (désactivé)
        if use_gpu is None:
            use_gpu = False
            
        # Créer la configuration de base
        config = {
            "primary": [os.path.join(input_path, f).replace("\\", "/") for f in frames],
            "aux": {
                "diffuse": [],
                "specular": [],
                "albedo": [{"paths": [os.path.join(input_path, f).replace("\\", "/") for f in frames], "layers": ["albedo"], "output-dir": aux_albedo_dir.replace("\\", "/")}],
                "Ci": [{"paths": [os.path.join(input_path, f).replace("\\", "/") for f in frames], "layers": ["Ci"]}],
                "subsurface": [{"paths": [os.path.join(input_path, f).replace("\\", "/") for f in frames], "layers": ["subsurface"], "output-dir": aux_subsurface_dir.replace("\\", "/")}]
            },
            "config": {
                "passes": selected_aovs,
                "topology": topo,
                "parameters": param,
                "output-dir": temp_dir.replace("\\", "/"),
                "flow": False,
                "debug": False,
                "asymmetry": 0.0,
                "flow": self.crossframe_mode_button.isChecked(),
            }
        }
        
        # Ajouter les light groups à la configuration avec les bons dossiers de sortie
        for aov in selected_aovs:
            if aov in light_groups_config["diffuse"]:
                config["aux"]["diffuse"].append({
                    "paths": config["primary"],
                    "layers": [aov],
                    "output-dir": aux_diffuse_dir.replace("\\", "/")
                })
            elif aov in light_groups_config["specular"]:
                config["aux"]["specular"].append({
                    "paths": config["primary"],
                    "layers": [aov],
                    "output-dir": aux_specular_dir.replace("\\", "/")
                })
                
        return config

# Ajouter cette classe complète juste avant la fonction main()

class DenoiZer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DenoiZer v1.2")  # Mise à jour de la version
        self.resize(550, 900)
        self.setMinimumSize(550, 700)
        self.setMaximumSize(550, 1200)
        
        # Charger la police Minecrafter
        self.load_minecrafter_font()
        
        # Charger la configuration et les paramètres
        self.load_config()
        self.settings = QSettings("DenoiZer", "App")
        
        # Variable pour suivre les tâches en cours d'exécution
        self.running_tasks = 0
        
        # Définir le nombre maximum de tâches parallèles (séquentiel pour l'instant)
        self.max_parallel_tasks = 1

        # Définir le fond de la fenêtre principale en noir
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: #e0e0e0;
            }
        """)

        # Créer le layout principal
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
    
        # Définir l'icône de l'application
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "DenoiZer_icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            app = QApplication.instance()
            if app:
                app.setWindowIcon(QIcon(icon_path))
        
        # Créer le widget d'onglets
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        
        # Style pour les onglets - les intégrer visuellement
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 0px solid #3c3c3c;
                border-radius: 0px;
                padding: 0px;
                background-color: #1e1e1e;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #3c3c3c;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                padding: 5px 10px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #0078d7;
                color: white;
            }
            QTabBar::tab:hover {
                background-color: #3e3e3e;
            }
            QTabBar::close-button {
                image: url(close.png);
                subcontrol-position: right;
            }
            QTabBar::close-button:hover {
                background-color: #ff5252;
                border-radius: 2px;
            }
        """)
        
        # Ajouter un onglet "+"
        plus_tab_widget = QWidget()
        plus_tab_widget.setStyleSheet("background-color: transparent;")
        self.tab_widget.addTab(plus_tab_widget, "+")
        self.tab_widget.tabBarClicked.connect(self.handle_tab_click)
        
        # Créer le premier onglet
        self.add_new_tab()
        
        # Ajouter le widget d'onglets au layout principal
        main_layout.addWidget(self.tab_widget)
        

    

    
    def run_all_tabs(self):
        """Exécuter tous les onglets l'un après l'autre"""
        # Vérifier s'il y a des onglets à traiter
        tab_count = self.tab_widget.count() - 1  # Ne pas compter l'onglet "+"
        if tab_count <= 0:
            return
        
        # Demander confirmation
        reply = QMessageBox.question(
            self, 
            "Confirm Batch Denoising", 
            f"This will process all {tab_count} tabs. Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if reply == QMessageBox.No:
            return
        
        # Montrer un message de démarrage
        self.setWindowTitle("DenoiZer v1.2 - BATCH MODE")
        
        # Désactiver l'ajout/suppression d'onglets pendant le traitement
        self.tab_widget.setTabsClosable(False)
        
        # Déconnecter temporairement le gestionnaire de clic sur les onglets
        try:
            self.tab_widget.tabBarClicked.disconnect()
        except:
            pass
        
        # Créer une file d'attente de tous les onglets à traiter (sauf le "+")
        self.tab_queue = list(range(tab_count))
        
        # Réinitialiser les états des onglets
        for i in range(tab_count):
            tab_name = self.tab_widget.tabText(i)
            clean_name = tab_name
            for prefix in ["⚙️ ", "✅ ", "❌ "]:
                clean_name = clean_name.replace(prefix, "")
            self.tab_widget.setTabText(i, clean_name)
        
        # Réinitialiser le compteur de tâches en cours
        self.running_tasks = 0
        
        # Lancer les premières tâches en parallèle
        QTimer.singleShot(500, self.process_next_tab)
        
    def process_next_tab(self):
        """Traiter l'onglet suivant dans la file d'attente"""
        # Vérifier s'il reste des onglets à traiter
        if not hasattr(self, 'tab_queue') or not self.tab_queue:
            # S'il n'y a plus de tâches en attente et aucune en cours, on a terminé
            if self.running_tasks == 0:
                # Réactiver l'ajout/suppression d'onglets quand tout est terminé
                self.tab_widget.setTabsClosable(True)
                self.setWindowTitle("DenoiZer v1.2")
                try:
                    self.tab_widget.tabBarClicked.connect(self.handle_tab_click)
                except:
                    pass
                QMessageBox.information(self, "Batch Complete", "All denoising tasks have been completed!")
            return
        
        # Traitement séquentiel - une tâche à la fois
        if self.running_tasks >= 1:
            return
        
        # Récupérer le prochain onglet à traiter
        tab_index = self.tab_queue[0]  # Garder dans la file pour l'instant
        tab = self.tab_widget.widget(tab_index)
        
        if not tab:
            # Si l'onglet n'existe pas, le retirer et passer au suivant
            self.tab_queue.pop(0)
            QTimer.singleShot(100, self.process_next_tab)
            return
        
        # Sélectionner cet onglet pour que l'utilisateur voie le traitement en cours
        self.tab_widget.setCurrentIndex(tab_index)
        
        # Mettre à jour le titre de l'onglet pour indiquer qu'il est en cours de traitement
        current_tab_name = self.tab_widget.tabText(tab_index)
        clean_name = current_tab_name
        for prefix in ["⚙️ ", "✅ ", "❌ "]:
            clean_name = clean_name.replace(prefix, "")
        self.tab_widget.setTabText(tab_index, f"⚙️ {clean_name}")
        
        # Augmenter le compteur de tâches en cours
        self.running_tasks += 1
        
        # Force l'interface à se mettre à jour
        QApplication.processEvents()
        
        # Configurer un callback pour quand le traitement est terminé
        tab.batch_finished_callback = self.tab_process_finished
        tab.batch_tab_index = tab_index
        tab.batch_tab_name = clean_name
        
        # Retirer l'onglet de la file
        self.tab_queue.pop(0)
        
        # Démarrer le traitement de cet onglet
        # Utiliser un timer pour s'assurer que l'UI est mise à jour avant de commencer
        QTimer.singleShot(500, lambda: tab.run_denoise(batch_mode=True))
        
        # Traitement séquentiel - pas de parallélisme
        # Le prochain onglet sera traité quand celui-ci sera terminé

    def tab_process_finished(self, tab_index, success=True):
        """Callback appelé quand un onglet a terminé son traitement"""
        # Récupérer l'onglet
        tab = self.tab_widget.widget(tab_index)
        if not tab:
            # Si l'onglet n'existe plus, passer au suivant
            self.running_tasks -= 1
            QTimer.singleShot(100, self.process_next_tab)
            return
        
        # Mettre à jour le titre de l'onglet
        prefix = "✅" if success else "❌"
        tab_name = tab.batch_tab_name if hasattr(tab, 'batch_tab_name') else self.tab_widget.tabText(tab_index).replace("⚙️ ", "").replace("✅ ", "").replace("❌ ", "")
        self.tab_widget.setTabText(tab_index, f"{prefix} {tab_name}")
        
        # Diminuer le compteur de tâches en cours
        self.running_tasks -= 1
        
        # S'assurer que l'interface est mise à jour
        QApplication.processEvents()
        
        # Lancer le prochain onglet si possible
        if self.tab_queue and self.running_tasks < self.max_parallel_tasks:
            QTimer.singleShot(500, self.process_next_tab)
        elif not self.tab_queue and self.running_tasks == 0:
            # Si tous les onglets ont été traités
            self.tab_widget.setTabsClosable(True)
            self.setWindowTitle("DenoiZer v1.2")
            try:
                self.tab_widget.tabBarClicked.connect(self.handle_tab_click)
            except:
                pass
            QMessageBox.information(self, "Batch Complete", "All denoising tasks have been completed!")

    def load_minecrafter_font(self):
        """Charger la police Cute Pixel depuis le fichier local"""
        try:
            # Essayer d'abord Cute Pixel
            font_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "CutePixel.ttf")
            if not os.path.exists(font_path):
                # Fallback vers Minecrafter si Cute Pixel n'existe pas
                font_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "Minecrafter.Alt.ttf")
            
            if os.path.exists(font_path):
                font_id = QFontDatabase.addApplicationFont(font_path)
                if font_id != -1:
                    font_families = QFontDatabase.applicationFontFamilies(font_id)
                    if font_families:
                        self.loaded_font_family = font_families[0]  # Stocker le nom exact de la police
                        print(f"✅ Police chargée: {self.loaded_font_family}")
                        return True
                    else:
                        print("⚠️ Impossible de charger la police")
                else:
                    print("⚠️ Erreur lors du chargement de la police")
            else:
                print("⚠️ Fichier de police non trouvé")
        except Exception as e:
            print(f"⚠️ Erreur lors du chargement de la police: {e}")
        
        # Fallback vers police système
        self.loaded_font_family = "Courier New"
        return False
    
    def load_config(self):
        """Charger la configuration globale"""
        try:
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_config.json")
            with open(config_path, "r") as f:
                self.config = json.load(f)
        except:
            self.config = {
                "COMPRESSION_MODE": "ZIP_COMPRESSION",
                "RENDERMAN_PROSERVER": "",
                "ENABLE_INTEGRATOR": False,
                "LIGHT_GROUP_PREFIX": "LGT",
                "ENABLE_SHADOWS": False,
                "SHADOWS_AOV_NAME": "SHADOWS",
                "ENABLE_CROSSFRAME": True,     # CrossFrame activé par défaut
                "USE_GPU": False               # GPU désactivé par défaut
            }
            
    def save_config(self):
        """Sauvegarder la configuration dans user_config.json"""
        try:
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_config.json")
            with open(config_path, "w") as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Error saving configuration file : {e}")
    
    def add_new_tab(self):
        """Ajouter un nouvel onglet de débruitage"""
        # Compter combien d'onglets réels nous avons
        tab_count = self.tab_widget.count() - 1  # -1 pour ne pas compter l'onglet "+"
        
        # Le nouveau nom sera toujours le prochain numéro dans la séquence
        tab_name = f"Task {tab_count + 1}"
        
        # Créer un nouvel onglet avec sa propre configuration
        new_tab = DenoizerTab(self, tab_name=tab_name, config=self.config.copy(), settings=self.settings)
        
        # Insérer le nouvel onglet avant l'onglet "+"
        self.tab_widget.insertTab(self.tab_widget.count() - 1, new_tab, tab_name)
        
        # Sélectionner le nouvel onglet
        self.tab_widget.setCurrentIndex(self.tab_widget.count() - 2)
        
        # Mettre à jour le texte du bouton DENOIZE
        self.update_denoize_button_text()
    
    def close_tab(self, index):
        """Fermer un onglet"""
        # Ne pas fermer l'onglet "+"
        if index == self.tab_widget.count() - 1:
            return
        
        # Confirmer la fermeture si c'est le dernier onglet
        if self.tab_widget.count() > 2:  # Plus d'un onglet réel + "+"
            # Récupérer l'index courant avant la suppression
            current_index = self.tab_widget.currentIndex()
            
            # Récupérer le widget de l'onglet et le supprimer
            tab_widget = self.tab_widget.widget(index)
            self.tab_widget.removeTab(index)
            
            # Renuméroter les onglets restants
            self.renumber_tabs()
            
            # Déterminer le nouvel index à sélectionner
            new_index = index
            if index >= self.tab_widget.count() - 1:
                # Si on a supprimé le dernier onglet de travail, sélectionner l'onglet précédent
                new_index = self.tab_widget.count() - 2
            
            # Sélectionner l'onglet approprié pour éviter de rester sur l'onglet "+"
            self.tab_widget.setCurrentIndex(new_index)
            
            # Libérer les ressources du widget
            if tab_widget:
                tab_widget.deleteLater()
        else:
            # Ne pas permettre de fermer le dernier onglet
            QMessageBox.information(self, "Information", "Cannot close the last tab.")
            
        # Mettre à jour le texte du bouton DENOIZE
        self.update_denoize_button_text()
    
    def renumber_tabs(self):
        """Renuméroter les onglets pour qu'ils soient toujours Task 1, Task 2, etc."""
        for i in range(self.tab_widget.count() - 1):  # Ne pas compter l'onglet "+"
            current_name = self.tab_widget.tabText(i)
            
            # Préserver les préfixes d'état (✅, ⚙️, ❌)
            prefix = ""
            if "⚙️ " in current_name:
                prefix = "⚙️ "
            elif "✅ " in current_name:
                prefix = "✅ "
            elif "❌ " in current_name:
                prefix = "❌ "
            
            # Remplacer le nom par Task N+1
            new_name = f"{prefix}Task {i+1}"
            self.tab_widget.setTabText(i, new_name)
            
            # Mettre à jour le nom interne du tab
            tab = self.tab_widget.widget(i)
            if tab and hasattr(tab, 'tab_name'):
                tab.tab_name = f"Task {i+1}"
    
    def handle_tab_click(self, index):
        """Gérer le clic sur un onglet"""
        # Si c'est l'onglet "+", ajouter un nouvel onglet
        if index == self.tab_widget.count() - 1:
            self.add_new_tab()
    
    def update_denoize_button_text(self):
        """Mettre à jour le texte du bouton DENOIZE en fonction du nombre d'onglets"""
        for i in range(self.tab_widget.count() - 1):  # Ne pas compter l'onglet "+"
            tab = self.tab_widget.widget(i)
            if hasattr(tab, 'run_btn'):
                if self.tab_widget.count() > 2:  # Plus d'un onglet réel
                    tab.run_btn.setText("DENOIZE ALL")
                else:
                    tab.run_btn.setText("DENOIZE")

def main():
    """Point d'entrée principal de l'application"""
    app = QApplication([])
    
    # Initialiser le fichier de configuration s'il n'existe pas
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_config.json")
    if not os.path.exists(config_path):
        default_config = {
            "COMPRESSION_MODE": "ZIP_COMPRESSION",
            "RENDERMAN_PROSERVER": "",
            "ENABLE_INTEGRATOR": False,
            "LIGHT_GROUP_PREFIX": "LGT",
            "ENABLE_SHADOWS": False,
            "SHADOWS_AOV_NAME": "SHADOWS",
            "ENABLE_CROSSFRAME": True,     # CrossFrame activé par défaut
        }
        try:
            with open(config_path, "w") as f:
                json.dump(default_config, f, indent=2)
        except Exception as e:
            print(f"Error creating configuration file : {e}")
    
    window = DenoiZer()
    window.show()
    # Modifier pour utiliser exec() au lieu de exec_()
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
