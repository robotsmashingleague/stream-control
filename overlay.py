import sys
import os
import json
import requests
import time
from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QLineEdit,
    QLabel, QHBoxLayout, QTabWidget, QSpinBox,
    QDialog, QDialogButtonBox, QFormLayout, QComboBox, QMessageBox, QCompleter,
    QRadioButton, QButtonGroup
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QFont

CONFIG_FILE = "overlay_config.json"

class OverlayWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Combat Overlay")
        self.resize(1920, 1080)
        self.setWindowFlags(Qt.WindowStaysOnTopHint)

        self.browser = QWebEngineView()
        
        # Enable settings for loading external content
        settings = self.browser.page().settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.AllowRunningInsecureContent, True)
        
        local_file = os.path.abspath("overlay.html")
        self.browser.load(QUrl.fromLocalFile(local_file))

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.browser)
        self.setLayout(layout)

        self.is_fullscreen = False
        
        # Set up auto-refresh checker timer
        self.refresh_checker = QTimer()
        self.refresh_checker.timeout.connect(self.check_for_refresh_request)
        self.refresh_checker.start(500)  # Check every 500ms

    def toggle_fullscreen(self):
        if self.is_fullscreen:
            self.setWindowFlags(Qt.WindowStaysOnTopHint)
            self.showNormal()
            self.is_fullscreen = False
        else:
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
            self.showFullScreen()
            self.is_fullscreen = True

    def update_timer(self, seconds, paused):
        script = f"updateTimer({seconds}, {str(paused).lower()});"
        self.browser.page().runJavaScript(script)

    def update_names(self, left_name, right_name):
        script = f"updateNameBoxes({json.dumps(left_name)}, {json.dumps(right_name)});"
        self.browser.page().runJavaScript(script)

    def update_background_color(self, color):
        self.browser.page().runJavaScript(f"document.body.style.backgroundColor = '{color}'")

    def update_name_colors(self, left_color, right_color):
        self.browser.page().runJavaScript(f"document.getElementById('left-name').style.backgroundColor = '{left_color}'")
        self.browser.page().runJavaScript(f"document.getElementById('right-name').style.backgroundColor = '{right_color}'")
    
    def switch_scene(self, scene_name):
        script = f"switchScene('{scene_name}');"
        self.browser.page().runJavaScript(script)
    
    def update_fight_cards(self, left_robot_data, right_robot_data, tournament_data=None):
        if tournament_data is None:
            tournament_data = {
                "tournament_name": getattr(self, 'current_tournament_name', 'Tournament Name'),
                "weight_class": "Weight Class"  # We'll need to add this data later
            }
        script = f"updateFightCards({json.dumps(left_robot_data)}, {json.dumps(right_robot_data)}, {json.dumps(tournament_data)});"
        self.browser.page().runJavaScript(script)
    
    def update_judges(self, left_robot_data, right_robot_data):
        script = f"updateJudges({json.dumps(left_robot_data)}, {json.dumps(right_robot_data)});"
        self.browser.page().runJavaScript(script)
    
    def update_rsl(self, tournament_data):
        script = f"updateRSL({json.dumps(tournament_data)});"
        self.browser.page().runJavaScript(script)
    
    def update_winner_red(self, robot_data):
        script = f"updateWinnerRed({json.dumps(robot_data)});"
        self.browser.page().runJavaScript(script)
    
    def update_winner_blue(self, robot_data):
        script = f"updateWinnerBlue({json.dumps(robot_data)});"
        self.browser.page().runJavaScript(script)
    
    def update_match_queue(self, tournament_data):
        script = f"updateMatchQueue({json.dumps(tournament_data)});"
        self.browser.page().runJavaScript(script)
    
    def refresh_match_queue(self):
        """Called by auto-refresh timer to update match queue data"""
        # This will be called from the control window's timer
        if hasattr(self, 'control_window') and self.control_window:
            self.control_window.refresh_match_queue_data()
    
    def check_for_refresh_request(self):
        """Check if JavaScript has requested a match queue refresh"""
        script = """
        (function() {
            if (window.requestMatchQueueRefresh) {
                window.requestMatchQueueRefresh = false;
                return true;
            }
            return false;
        })();
        """
        self.browser.page().runJavaScript(script, self.handle_refresh_request)
    
    def handle_refresh_request(self, should_refresh):
        """Handle the result of the refresh request check"""
        if should_refresh:
            self.refresh_match_queue()
    
    def update_match_scene(self, left_robot_data, right_robot_data):
        script = f"updateMatchScene({json.dumps(left_robot_data)}, {json.dumps(right_robot_data)});"
        self.browser.page().runJavaScript(script)

class ControlWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Overlay Control")

        # Initialize tournaments and robots data storage FIRST
        self.tournaments_data = {}
        self.robots_data = {}
        self.operational_data = []
        self.matches_data = []
        self.current_tournament_id = None
        self.data_loaded = False
        self.current_match = None
        self.retained_completed_match = None  # Store completed match until another is selected

        self.default_duration = 120
        self.default_bg_color = "#00FF00"
        self.left_color = "#C22E2E"
        self.right_color = "#2D5FCC"
        self.last_tournament = None
        self.current_tournament_name = None
        self.last_left_competitor = None
        self.last_right_competitor = None

        self.load_config()

        self.overlay_window = OverlayWindow()
        self.overlay_window.control_window = self  # Add reference for auto-refresh
        self.overlay_window.show()
        self.overlay_window.update_background_color(self.default_bg_color)
        self.overlay_window.update_name_colors(self.left_color, self.right_color)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.create_timer_tab(), "Main")
        self.tabs.addTab(self.create_settings_tab(), "Settings")

        layout = QVBoxLayout()
        layout.addWidget(self.tabs)

        self.reopen_button = QPushButton("Open Overlay")
        self.reopen_button.clicked.connect(self.reopen_overlay)
        
        # Style for overlay control buttons (double height, 1.5x text)
        overlay_button_font = QFont()
        overlay_button_font.setPointSize(int(overlay_button_font.pointSize() * 1.5))
        
        self.reopen_button.setFont(overlay_button_font)
        self.reopen_button.setMinimumHeight(60)  # Double height
        
        # Create horizontal layout for overlay control buttons
        overlay_controls_layout = QHBoxLayout()
        overlay_controls_layout.addWidget(self.reopen_button)
        overlay_controls_layout.addWidget(self.fullscreen_button)
        layout.addLayout(overlay_controls_layout)

        self.setLayout(layout)
        self.resize(400, 420)
        self.show()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_timer_countdown)
        self.remaining_time = 0
        self.is_paused = False

        # Auto-update timer for matches (1 second interval)
        self.auto_update_timer = QTimer(self)
        self.auto_update_timer.timeout.connect(self.auto_update_matches)
        self.auto_update_timer.setSingleShot(False)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                self.default_bg_color = config.get("background_color", self.default_bg_color)
                self.default_duration = config.get("timer_duration", self.default_duration)
                self.left_color = config.get("left_color", self.left_color)
                self.right_color = config.get("right_color", self.right_color)
                self.last_tournament = config.get("last_tournament", None)
                self.last_left_competitor = config.get("last_left_competitor", None)
                self.last_right_competitor = config.get("last_right_competitor", None)

    def save_config(self):
        # Get current competitor selections
        left_competitor = None
        right_competitor = None
        if hasattr(self, 'left_competitor_dropdown') and hasattr(self, 'right_competitor_dropdown'):
            left_text = self.left_competitor_dropdown.currentText()
            right_text = self.right_competitor_dropdown.currentText()
            # Only save if not placeholder text
            if left_text and not left_text.startswith("-- Select"):
                left_competitor = left_text
            if right_text and not right_text.startswith("-- Select"):
                right_competitor = right_text
        
        config = {
            "background_color": self.default_bg_color,
            "timer_duration": self.default_duration,
            "left_color": self.left_color,
            "right_color": self.right_color,
            "last_tournament": getattr(self, 'current_tournament_name', None),
            "last_left_competitor": left_competitor,
            "last_right_competitor": right_competitor
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)

    def create_timer_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()

        self.left_competitor_dropdown = QComboBox()
        self.left_competitor_dropdown.setEditable(True)
        self.left_competitor_dropdown.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.left_competitor_dropdown.completer().setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.left_competitor_dropdown.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        self.left_competitor_dropdown.setPlaceholderText("Type to filter left competitor...")
        self.left_competitor_dropdown.addItem("-- Select Left Competitor --")

        self.right_competitor_dropdown = QComboBox()
        self.right_competitor_dropdown.setEditable(True)
        self.right_competitor_dropdown.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.right_competitor_dropdown.completer().setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.right_competitor_dropdown.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        self.right_competitor_dropdown.setPlaceholderText("Type to filter right competitor...")
        self.right_competitor_dropdown.addItem("-- Select Right Competitor --")

        # The built-in QComboBox filtering handles most functionality automatically
        
        # Connect competitor selection changes to save config
        self.left_competitor_dropdown.currentTextChanged.connect(self.on_competitor_changed)
        self.right_competitor_dropdown.currentTextChanged.connect(self.on_competitor_changed)
        
        self.name_button = QPushButton("Update")
        self.name_button.clicked.connect(self.update_names)
        
        # Style update button with double height and larger text
        update_button_font = QFont()
        update_button_font.setPointSize(int(update_button_font.pointSize() * 1.5))
        self.name_button.setFont(update_button_font)
        self.name_button.setMinimumHeight(60)  # Double height
        # Make button width fit text content
        self.name_button.adjustSize()
        self.name_button.setMaximumWidth(self.name_button.sizeHint().width())

        self.start_timer_button = QPushButton("▶")
        self.start_timer_button.clicked.connect(self.start_timer)
        self.start_timer_button.setFixedSize(60, 60)  # 1.5x larger (40 * 1.5 = 60)
        self.start_timer_button.setToolTip("Start Timer")

        self.pause_timer_button = QPushButton("⏸")  # Proper pause symbol
        self.pause_timer_button.clicked.connect(self.pause_timer)
        self.pause_timer_button.setFixedSize(60, 60)  # 1.5x larger
        self.pause_timer_button.setToolTip("Pause Timer")

        self.edit_timer_button = QPushButton("Set\nCustom")
        self.edit_timer_button.clicked.connect(self.set_timer_value)
        self.edit_timer_button.setFixedSize(80, 60)  # Wider to accommodate text, same height

        self.reset_timer_button = QPushButton("⏹")  # Proper stop/reset symbol
        self.reset_timer_button.clicked.connect(self.reset_timer)
        self.reset_timer_button.setFixedSize(60, 60)  # 1.5x larger
        self.reset_timer_button.setToolTip("Reset Timer")
        
        # Style timer control buttons with larger icons and no blue
        timer_button_style = """
        QPushButton {
            font-size: 28px;
            color: black;
            background-color: #f0f0f0;
            border: 2px solid #888;
            border-radius: 5px;
        }
        QPushButton:hover {
            background-color: #e0e0e0;
            border-color: #666;
        }
        QPushButton:pressed {
            background-color: #d0d0d0;
            border-color: #444;
        }
        """
        
        self.start_timer_button.setStyleSheet(timer_button_style)
        self.pause_timer_button.setStyleSheet(timer_button_style)
        self.reset_timer_button.setStyleSheet(timer_button_style)
        
        # Style the edit timer button with smaller font for two-line text
        edit_timer_style = """
        QPushButton {
            font-size: 14px;
            color: black;
            background-color: #f0f0f0;
            border: 2px solid #888;
            border-radius: 5px;
        }
        QPushButton:hover {
            background-color: #e0e0e0;
            border-color: #666;
        }
        QPushButton:pressed {
            background-color: #d0d0d0;
            border-color: #444;
        }
        """
        self.edit_timer_button.setStyleSheet(edit_timer_style)

        # Style for overlay control buttons (double height, 1.5x text)
        overlay_button_font = QFont()
        overlay_button_font.setPointSize(int(overlay_button_font.pointSize() * 1.5))

        self.fullscreen_button = QPushButton("Fullscreen")
        self.fullscreen_button.clicked.connect(self.overlay_window.toggle_fullscreen)
        self.fullscreen_button.setFont(overlay_button_font)
        self.fullscreen_button.setMinimumHeight(60)  # Double height

        # Scene selection buttons
        self.match_scene_button = QPushButton("Match")
        self.match_scene_button.clicked.connect(self.show_match_scene)
        
        self.fight_cards_button = QPushButton("Fight Cards")
        self.fight_cards_button.clicked.connect(self.show_fight_cards_scene)
        
        self.judges_button = QPushButton("Judges")
        self.judges_button.clicked.connect(self.show_judges_scene)
        
        self.rsl_button = QPushButton("RSL")
        self.rsl_button.clicked.connect(self.show_rsl_scene)
        
        self.winner_red_button = QPushButton("Winner Red")
        self.winner_red_button.clicked.connect(self.show_winner_red_scene)
        
        self.winner_blue_button = QPushButton("Winner Blue")
        self.winner_blue_button.clicked.connect(self.show_winner_blue_scene)

        self.match_queue_button = QPushButton("Match Queue")
        self.match_queue_button.clicked.connect(self.show_match_queue_scene)

        # Scene Selection Section
        # Create larger font for section titles (2x default size)
        section_font = QFont()
        section_font.setPointSize(int(section_font.pointSize() * 2))
        section_font.setBold(True)
        
        scenes_label = QLabel("Scenes")
        scenes_label.setFont(section_font)
        layout.addWidget(scenes_label)
        
        # Set double height for all scene buttons
        button_height = 60
        
        # Create larger font for scene buttons (1.8x default size)
        button_font = QFont()
        button_font.setPointSize(int(button_font.pointSize() * 1.8))
        
        # Apply styling to scene buttons
        scene_buttons = [
            self.match_scene_button, self.fight_cards_button, self.judges_button, 
            self.rsl_button, self.winner_red_button, self.winner_blue_button, self.match_queue_button
        ]
        
        for button in scene_buttons:
            button.setMinimumHeight(button_height)
            button.setFont(button_font)
        
        # First row: Match and RSL
        first_row_layout = QHBoxLayout()
        first_row_layout.addWidget(self.match_scene_button)
        first_row_layout.addWidget(self.rsl_button)
        layout.addLayout(first_row_layout)
        
        # Second row: Fight Cards and Judges
        second_row_layout = QHBoxLayout()
        second_row_layout.addWidget(self.fight_cards_button)
        second_row_layout.addWidget(self.judges_button)
        layout.addLayout(second_row_layout)
        
        # Third row: Winners
        winner_layout = QHBoxLayout()
        winner_layout.addWidget(self.winner_red_button)
        winner_layout.addWidget(self.winner_blue_button)
        layout.addLayout(winner_layout)
        
        # Fourth row: Match Queue (centered)
        queue_layout = QHBoxLayout()
        queue_layout.addStretch()
        queue_layout.addWidget(self.match_queue_button)
        queue_layout.addStretch()
        layout.addLayout(queue_layout)
        layout.addSpacing(15)
        
        # Competitor Selection Section
        competitors_label = QLabel("Competitors")
        competitors_label.setFont(section_font)
        layout.addWidget(competitors_label)
        
        # Manual/Auto toggle
        mode_layout = QHBoxLayout()
        self.manual_radio = QRadioButton("Manual")
        self.auto_radio = QRadioButton("Auto")
        self.manual_radio.setChecked(True)  # Default to manual
        
        # Style manual/auto radio buttons with 1.3x larger text
        mode_font = QFont()
        mode_font.setPointSize(int(mode_font.pointSize() * 1.3))
        self.manual_radio.setFont(mode_font)
        self.auto_radio.setFont(mode_font)
        
        self.selection_mode_group = QButtonGroup()
        self.selection_mode_group.addButton(self.manual_radio)
        self.selection_mode_group.addButton(self.auto_radio)
        
        # Connect mode change to update UI
        self.manual_radio.toggled.connect(self.on_selection_mode_changed)
        
        mode_layout.addWidget(self.manual_radio)
        mode_layout.addWidget(self.auto_radio)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)
        
        # Create font for dropdown text (2x size)
        dropdown_font = QFont()
        dropdown_font.setPointSize(int(dropdown_font.pointSize() * 2))
        
        # Auto mode display (initially hidden)
        self.auto_match_dropdown = QComboBox()
        self.auto_match_dropdown.addItem("No matches available")
        self.auto_match_dropdown.currentTextChanged.connect(self.on_match_selection_changed)
        self.auto_match_dropdown.setFont(dropdown_font)  # Apply 2x font size
        self.auto_match_dropdown.setVisible(False)
        layout.addWidget(self.auto_match_dropdown)
        
        self.refresh_matches_button = QPushButton("Refresh Matches")
        self.refresh_matches_button.clicked.connect(self.load_and_auto_select_match)
        self.refresh_matches_button.setVisible(False)
        layout.addWidget(self.refresh_matches_button)
        
        # Manual competitor selection controls
        competitor_layout = QHBoxLayout()
        
        # Create font for competitor labels (1.3x size)
        competitor_label_font = QFont()
        competitor_label_font.setPointSize(int(competitor_label_font.pointSize() * 1.3))
        
        left_layout = QVBoxLayout()
        self.left_competitor_label = QLabel("Red")
        self.left_competitor_label.setFont(competitor_label_font)
        left_layout.addWidget(self.left_competitor_label)
        self.left_competitor_dropdown.setFont(dropdown_font)
        # Style the completer popup for typing/filtering
        self.left_competitor_dropdown.completer().popup().setFont(dropdown_font)
        # Style the line edit (text input field) within the dropdown
        self.left_competitor_dropdown.lineEdit().setFont(dropdown_font)
        left_layout.addWidget(self.left_competitor_dropdown)
        
        right_layout = QVBoxLayout()
        self.right_competitor_label = QLabel("Blue")
        self.right_competitor_label.setFont(competitor_label_font)
        right_layout.addWidget(self.right_competitor_label)
        self.right_competitor_dropdown.setFont(dropdown_font)
        # Style the completer popup for typing/filtering
        self.right_competitor_dropdown.completer().popup().setFont(dropdown_font)
        # Style the line edit (text input field) within the dropdown
        self.right_competitor_dropdown.lineEdit().setFont(dropdown_font)
        right_layout.addWidget(self.right_competitor_dropdown)
        
        competitor_layout.addLayout(left_layout)
        competitor_layout.addLayout(right_layout)
        
        layout.addLayout(competitor_layout)
        
        # Center the update button horizontally
        update_button_layout = QHBoxLayout()
        update_button_layout.addStretch()
        update_button_layout.addWidget(self.name_button)
        update_button_layout.addStretch()
        layout.addLayout(update_button_layout)
        layout.addSpacing(15)
        
        # Timer Controls Section
        timer_label = QLabel("Timer Controls")
        timer_label.setFont(section_font)
        layout.addWidget(timer_label)
        timer_controls_layout = QHBoxLayout()
        timer_controls_layout.addWidget(self.start_timer_button)
        timer_controls_layout.addWidget(self.pause_timer_button)
        timer_controls_layout.addWidget(self.reset_timer_button)
        timer_controls_layout.addWidget(self.edit_timer_button)
        timer_controls_layout.addStretch()
        layout.addLayout(timer_controls_layout)
        layout.addSpacing(15)

        tab.setLayout(layout)
        return tab

    def create_settings_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()

        self.bg_color_input = QLineEdit(self.default_bg_color)
        self.bg_color_input.setPlaceholderText("Background Color (e.g. #00FF00)")

        self.left_color_input = QLineEdit(self.left_color)
        self.left_color_input.setPlaceholderText("Left Name Color")

        self.right_color_input = QLineEdit(self.right_color)
        self.right_color_input.setPlaceholderText("Right Name Color")

        self.bg_color_button = QPushButton("Apply Colors")
        self.bg_color_button.clicked.connect(self.apply_colors)

        self.reset_colors_button = QPushButton("Reset to Default Colors")
        self.reset_colors_button.clicked.connect(self.reset_to_defaults)

        self.duration_input = QSpinBox()
        self.duration_input.setRange(10, 3600)
        self.duration_input.setValue(self.default_duration)
        self.duration_input.setSuffix(" sec")

        self.duration_label = QLabel("Default Timer Duration")

        layout.addWidget(QLabel("Background Color for Chroma Key"))
        layout.addWidget(self.bg_color_input)
        layout.addWidget(QLabel("Name Box Colors"))
        layout.addWidget(self.left_color_input)
        layout.addWidget(self.right_color_input)
        layout.addWidget(self.bg_color_button)
        layout.addWidget(self.reset_colors_button)
        layout.addSpacing(10)
        layout.addWidget(self.duration_label)
        layout.addWidget(self.duration_input)
        
        # Tournament Selection Section
        layout.addSpacing(20)
        layout.addWidget(QLabel("Tournament Selection"))
        
        # Tournament dropdown
        self.tournament_dropdown = QComboBox()
        layout.addWidget(self.tournament_dropdown)
        
        # Refresh button
        self.refresh_tournaments_button = QPushButton("Refresh Tournament List")
        self.refresh_tournaments_button.clicked.connect(self.load_all_data)
        layout.addWidget(self.refresh_tournaments_button)
        
        # Tournament info display (smaller)
        self.tournament_info_label = QLabel("No tournament selected")
        self.tournament_info_label.setWordWrap(True)
        self.tournament_info_label.setStyleSheet("QLabel { background-color: #f0f0f0; color: #333333; padding: 8px; border: 1px solid #ccc; font-size: 11px; }")
        self.tournament_info_label.setMaximumHeight(80)
        layout.addWidget(self.tournament_info_label)
        
        tab.setLayout(layout)
        
        # Load all data on initialization - tournaments first, then robot data
        # Signal connection will be made in load_tournaments() after data is ready
        self.load_all_data()
        
        return tab

    def load_tournaments(self):
        """Load tournaments from the API"""
        self.tournament_info_label.setText("Loading tournaments...")
        try:
            response = requests.get("https://rslcheckin.replit.app/api/tournaments", timeout=10)
            response.raise_for_status()
            data = response.json()
            
            print(f"API Response: {data}")  # Debug output
            
            # Temporarily disconnect signal to prevent premature triggering
            try:
                self.tournament_dropdown.currentTextChanged.disconnect()
            except:
                pass  # Might not be connected yet
                
            # Clear existing items and data
            self.tournament_dropdown.clear()
            self.tournaments_data.clear()
                
            # Add a placeholder item first
            self.tournament_dropdown.addItem("-- Select Tournament --")
            
            if data.get("success") and data.get("tournaments"):
                for tournament in data["tournaments"]:
                    tournament_name = tournament["name"]
                    self.tournament_dropdown.addItem(tournament_name)
                    # Store full tournament data for later use
                    self.tournaments_data[tournament_name] = tournament
                    
                self.tournament_info_label.setText(f"Loaded {len(data['tournaments'])} tournaments")
                print(f"Loaded tournaments: {list(self.tournaments_data.keys())}")  # Debug output
                
                # Set data loaded flag for tournaments
                self.data_loaded = True
                print(f"Data loaded flag set to: {self.data_loaded}")  # Debug output
            else:
                self.tournament_info_label.setText("No tournaments found")
                self.data_loaded = False
                
            print(f"About to reconnect signal. Data loaded: {self.data_loaded}")  # Debug output
            # Reconnect the signal after data is loaded
            self.tournament_dropdown.currentTextChanged.connect(self.on_tournament_selected)
            print("Signal reconnected successfully")  # Debug output
            
            # Restore last selected tournament if available
            QTimer.singleShot(200, self.restore_last_tournament)
                
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error: {str(e)}"
            print(f"Network error in load_tournaments: {error_msg}")
            QMessageBox.warning(self, "Connection Error", error_msg)
            self.tournament_info_label.setText(error_msg)
            self.data_loaded = False
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            print(f"General error in load_tournaments: {error_msg}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "Error", error_msg)
            self.tournament_info_label.setText(error_msg)
            self.data_loaded = False

    def restore_last_tournament(self):
        """Restore the last selected tournament from configuration"""
        if self.last_tournament and self.last_tournament in self.tournaments_data:
            print(f"Restoring last tournament: {self.last_tournament}")
            # Find the index of the last tournament in the dropdown
            index = self.tournament_dropdown.findText(self.last_tournament)
            if index >= 0:
                self.tournament_dropdown.setCurrentIndex(index)
                print(f"Tournament '{self.last_tournament}' restored successfully")
            else:
                print(f"Tournament '{self.last_tournament}' not found in dropdown")
        else:
            print(f"No valid last tournament to restore. Last tournament: {self.last_tournament}")

    def load_all_data(self):
        """Load all data in proper sequence"""
        print("Starting data loading sequence...")
        try:
            self.load_tournaments()  # This will set data_loaded = True if successful
            self.load_robots_data()
            self.load_operational_data()
            print("All data loading completed successfully")
        except Exception as e:
            print(f"Error during data loading: {e}")
            self.tournament_info_label.setText(f"Error loading data: {e}")
            self.data_loaded = False

    def on_tournament_selected(self, tournament_name):
        """Handle tournament selection"""
        print(f"Tournament selected: '{tournament_name}'")  # Debug output
        print(f"Available tournament data keys: {list(self.tournaments_data.keys())}")  # Debug output
        
        # Ignore placeholder selection or empty selection
        if tournament_name == "-- Select Tournament --" or not tournament_name:
            self.tournament_info_label.setText("No tournament selected")
            self.current_tournament_id = None
            self.clear_competitor_dropdowns()
            return
            
        # Check if data is loaded
        if not self.data_loaded or not self.tournaments_data:
            self.tournament_info_label.setText("Tournament data not loaded yet. Please try refreshing.")
            print(f"Data loaded flag: {self.data_loaded}, Tournament data size: {len(self.tournaments_data)}")
            return
            
        if tournament_name in self.tournaments_data:
            tournament = self.tournaments_data[tournament_name]
            info_text = f"Selected: {tournament['name']}\nOrganizer: {tournament['event_organizer']}\nLocation: {tournament['location']}\nID: {tournament['id']}"
            self.tournament_info_label.setText(info_text)
            
            # Save current tournament selection
            self.current_tournament_name = tournament_name
            self.current_tournament_id = tournament['id']
            self.save_config()  # Save immediately when tournament is selected
            
            # Use a timer to delay the robot loading to avoid signal conflicts
            QTimer.singleShot(100, self.load_robots_for_tournament)
            
            # Load matches data if in auto mode
            if hasattr(self, 'auto_radio') and self.auto_radio.isChecked():
                QTimer.singleShot(200, self.load_and_auto_select_match)
        else:
            self.tournament_info_label.setText(f"Tournament '{tournament_name}' not found in loaded data. Try refreshing.")
            self.current_tournament_id = None
            self.clear_competitor_dropdowns()

    def load_robots_data(self):
        """Load all robots data from API with retry logic"""
        max_retries = 3
        retry_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    print(f"Retry attempt {attempt + 1}/{max_retries} for robots data...")
                    time.sleep(retry_delay)
                else:
                    print("Attempting to load robots data...")
                
                response = requests.get("https://rslcheckin.replit.app/api/robots", timeout=15)
                
                print(f"Response status code: {response.status_code}")
                if response.status_code != 200:
                    print(f"Response content: {response.text[:500]}...")
                    
                response.raise_for_status()
                data = response.json()
                
                self.robots_data = {}
                if data.get("robots"):  # Remove success check as API might not return success field
                    for robot in data["robots"]:
                        self.robots_data[robot["id"]] = robot
                    print(f"Successfully loaded {len(self.robots_data)} robots")
                    return  # Success, exit the retry loop
                else:
                    print(f"No robots found in API response. Data keys: {list(data.keys()) if data else 'No data'}")
                    
            except requests.exceptions.Timeout:
                print(f"Attempt {attempt + 1}: Request timed out after 15 seconds")
            except requests.exceptions.ConnectionError as e:
                print(f"Attempt {attempt + 1}: Connection failed - {e}")
            except requests.exceptions.HTTPError as e:
                print(f"Attempt {attempt + 1}: HTTP Error {e.response.status_code} - {e}")
                if e.response.status_code == 500:
                    print("Server is experiencing internal errors. This may be temporary.")
            except ValueError as e:
                print(f"Attempt {attempt + 1}: Invalid JSON response - {e}")
            except Exception as e:
                print(f"Attempt {attempt + 1}: Unexpected error - {e}")
                
            # If this was the last attempt, give up
            if attempt == max_retries - 1:
                print("Failed to load robots data after all retry attempts")
                self.robots_data = {}  # Ensure we have an empty dict to prevent crashes

    def load_operational_data(self):
        """Load operational data from API"""
        try:
            response = requests.get("https://rslcheckin.replit.app/api/operational", timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get("operational"):
                self.operational_data = data["operational"]
                
                # Debug: Show which robots have images
                print(f"Loaded {len(self.operational_data)} operational records")
                for op_record in self.operational_data:
                    robot_id = op_record.get("robot_id")
                    clean_image = op_record.get("clean_image")
                    raw_image = op_record.get("raw_image")
                    if clean_image or raw_image:
                        # Debug: print(f"Robot {robot_id} has images: clean={clean_image}, raw={raw_image}")
                        pass
            
        except Exception as e:
            print(f"Error loading operational data: {e}")

    def load_matches_data(self):
        """Load matches data from API"""
        try:
            if not self.current_tournament_id:
                print("No current tournament ID set, cannot load matches")
                return
                
            print(f"Loading matches for tournament ID: {self.current_tournament_id}")
            
            # Get pending matches for current tournament
            params = {
                "tournament_id": self.current_tournament_id,
                "status": "pending"
            }
            
            url = "https://rslcheckin.replit.app/api/matches"
            print(f"Making request to: {url} with params: {params}")
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            print(f"API response: {data}")
            
            if data.get("success") and data.get("matches"):
                self.matches_data = data["matches"]
                print(f"Loaded {len(self.matches_data)} pending matches for tournament {self.current_tournament_id}")
            else:
                self.matches_data = []
                print(f"No pending matches found. Response success: {data.get('success')}, matches key exists: {'matches' in data}")
                
        except Exception as e:
            print(f"Error loading matches data: {e}")
            self.matches_data = []

    def load_and_auto_select_match(self):
        """Load matches and automatically select the next pending match"""
        if not self.current_tournament_id:
            self.update_match_dropdown([])
            print("No tournament selected for auto mode")
            return
            
        # Load fresh matches data
        self.load_matches_data()
        
        if not self.matches_data:
            self.update_match_dropdown([])
            print("No pending matches available for auto selection")
            return
        
        # Sort matches by ID to get lowest match number first
        sorted_matches = sorted(self.matches_data, key=lambda x: x.get('id', 0))
        
        # Update dropdown with all matches
        self.update_match_dropdown(sorted_matches)
        
        # Get the lowest match number (first in sorted list)
        match = sorted_matches[0]
        self.current_match = match
        
        # Get robot names for the match
        robot1_id = match.get("robot_1_id")
        robot2_id = match.get("robot_2_id")
        
        robot1_name = self.get_robot_name_by_id(robot1_id)
        robot2_name = self.get_robot_name_by_id(robot2_id)
        
        if robot1_name and robot2_name:
            # Set the competitors (even though dropdowns are disabled, update them for display)
            self.set_competitor_selection(robot1_name, robot2_name)
            
            # Call the same update method that manual mode uses
            self.update_names()
            
            # Select this match in the dropdown
            match_text = f"{robot1_name} vs {robot2_name}"
            index = self.auto_match_dropdown.findText(match_text)
            if index >= 0:
                self.auto_match_dropdown.setCurrentIndex(index)
            
            print(f"Auto-selected match #{match.get('id')}: {robot1_name} vs {robot2_name}")
            print(f"ELO: {match.get('robot_1_elo_before', 'N/A')} vs {match.get('robot_2_elo_before', 'N/A')}")
        else:            
            print(f"Could not find robot names for match #{match.get('id')}")

    def get_robot_name_by_id(self, robot_id):
        """Get robot name by ID from loaded robots data"""
        if robot_id in self.robots_data:
            return self.robots_data[robot_id].get("bot_name")
        return None

    def set_competitor_selection(self, left_name, right_name):
        """Set competitor dropdown selections"""
        # Find and set left competitor
        left_index = self.left_competitor_dropdown.findText(left_name)
        if left_index >= 0:
            self.left_competitor_dropdown.setCurrentIndex(left_index)
        
        # Find and set right competitor  
        right_index = self.right_competitor_dropdown.findText(right_name)
        if right_index >= 0:
            self.right_competitor_dropdown.setCurrentIndex(right_index)

    def auto_update_overlay_with_match(self, match, robot1_name, robot2_name):
        """Automatically update the overlay with match data"""
        # Get robot data for the overlay
        robot1_data = self.get_robot_data_for_overlay(match.get("robot_1_id"))
        robot2_data = self.get_robot_data_for_overlay(match.get("robot_2_id"))
        
        if robot1_data and robot2_data:
            # Update overlay names
            self.overlay_window.browser.page().runJavaScript(f"""
                if (typeof updateMatchNames === 'function') {{
                    updateMatchNames('{robot1_name}', '{robot2_name}');
                }}
            """)
            
            # Update fight cards and match scenes with robot data
            tournament_data = {
                "tournament_name": getattr(self, 'current_tournament_name', 'Tournament Name'),
                "weight_class": "Weight Class"  # We'll need to add this data later
            }
            self.overlay_window.browser.page().runJavaScript(f"""
                if (typeof updateFightCards === 'function') {{
                    updateFightCards({json.dumps(robot1_data)}, {json.dumps(robot2_data)}, {json.dumps(tournament_data)});
                }}
            """)
            
            print(f"Auto-updated overlay with match data")

    def get_robot_data_for_overlay(self, robot_id):
        """Get complete robot data including images for overlay"""
        if robot_id not in self.robots_data:
            return None
            
        robot = self.robots_data[robot_id].copy()
        
        # Add image URL from operational data
        image_url = self.get_robot_image_url(robot_id)
        robot["image_url"] = image_url
        
        # Ensure weight_class is available (use from API data or default to 3lb)
        if 'weight_class' not in robot:
            robot['weight_class'] = '3lb'  # Default weight class
        
        return robot

    def update_match_dropdown(self, matches):
        """Update the match dropdown with available matches"""
        # Temporarily disconnect signal to avoid triggering selection change
        self.auto_match_dropdown.currentTextChanged.disconnect()
        
        # Clear existing items
        self.auto_match_dropdown.clear()
        
        # First, add retained completed match if it exists
        if self.retained_completed_match:
            match = self.retained_completed_match
            robot1_id = match.get("robot_1_id")
            robot2_id = match.get("robot_2_id")
            
            robot1_name = self.get_robot_name_by_id(robot1_id) or f"Robot {robot1_id}"
            robot2_name = self.get_robot_name_by_id(robot2_id) or f"Robot {robot2_id}"
            
            match_text = f"{robot1_name} vs {robot2_name} (COMPLETED)"
            self.auto_match_dropdown.addItem(match_text)
            self.auto_match_dropdown.setItemData(0, match)
        
        if not matches:
            if not self.retained_completed_match:
                self.auto_match_dropdown.addItem("No matches available")
        else:
            for match in matches:
                robot1_id = match.get("robot_1_id")
                robot2_id = match.get("robot_2_id")
                
                robot1_name = self.get_robot_name_by_id(robot1_id) or f"Robot {robot1_id}"
                robot2_name = self.get_robot_name_by_id(robot2_id) or f"Robot {robot2_id}"
                
                match_text = f"{robot1_name} vs {robot2_name}"
                self.auto_match_dropdown.addItem(match_text)
                
                # Store match data in the item
                self.auto_match_dropdown.setItemData(self.auto_match_dropdown.count() - 1, match)
        
        # Reconnect signal
        self.auto_match_dropdown.currentTextChanged.connect(self.on_match_selection_changed)

    def on_match_selection_changed(self):
        """Handle match selection changes and update overlay"""
        current_index = self.auto_match_dropdown.currentIndex()
        if current_index < 0:
            return
            
        # Get match data from the selected item
        match = self.auto_match_dropdown.itemData(current_index)
        if not match:
            return
            
        self.current_match = match
        
        # Clear retained completed match when a new match is selected
        if self.retained_completed_match and match.get('id') != self.retained_completed_match.get('id'):
            self.retained_completed_match = None
        
        # Get robot names
        robot1_id = match.get("robot_1_id")
        robot2_id = match.get("robot_2_id")
        robot1_name = self.get_robot_name_by_id(robot1_id)
        robot2_name = self.get_robot_name_by_id(robot2_id)
        
        if robot1_name and robot2_name:
            # Update competitor selections (even though disabled)
            self.set_competitor_selection(robot1_name, robot2_name)
            
            # Call the same update method that manual mode uses
            self.update_names()
            
            print(f"Selected match #{match.get('id')}: {robot1_name} vs {robot2_name}")

    def auto_update_matches(self):
        """Auto-update matches every second when in auto mode"""
        if not hasattr(self, 'auto_radio') or not self.auto_radio.isChecked():
            return
            
        if not self.current_tournament_id:
            return
            
        # Store current selection to maintain it after update
        current_text = self.auto_match_dropdown.currentText()
        current_match_id = None
        if self.current_match:
            current_match_id = self.current_match.get('id')
        
        # Load fresh matches data
        self.load_matches_data()
        
        # Check if current match became completed
        if self.current_match and current_match_id:
            # Look for the current match in the fresh data
            current_match_still_pending = False
            for match in self.matches_data:
                if match.get('id') == current_match_id:
                    current_match_still_pending = True
                    break
            
            # If current match is no longer in pending matches, it became completed
            if not current_match_still_pending and not self.retained_completed_match:
                self.retained_completed_match = self.current_match.copy()
                print(f"Match #{current_match_id} completed and retained in dropdown")
        
        if self.matches_data:
            # Sort matches by ID
            sorted_matches = sorted(self.matches_data, key=lambda x: x.get('id', 0))
            
            # Update dropdown
            self.update_match_dropdown(sorted_matches)
            
            # Try to restore previous selection
            index = self.auto_match_dropdown.findText(current_text)
            if index >= 0:
                self.auto_match_dropdown.setCurrentIndex(index)
            else:
                # If previous selection not found, default to lowest match number
                if self.auto_match_dropdown.count() > 0:
                    self.auto_match_dropdown.setCurrentIndex(0)

    def load_robots_for_tournament(self):
        """Load robots for the currently selected tournament"""
        if not self.current_tournament_id:
            return
            
        # Load robot and operational data if not already loaded
        if not self.robots_data:
            self.load_robots_data()
        if not self.operational_data:
            self.load_operational_data()
        
        # Find robots in this tournament
        tournament_robots = []
        for op_record in self.operational_data:
            if op_record.get("tournament_id") == self.current_tournament_id:
                robot_id = op_record.get("robot_id")
                if robot_id in self.robots_data:
                    robot = self.robots_data[robot_id]
                    tournament_robots.append(robot["bot_name"])
        
        # Update competitor dropdowns
        self.update_competitor_dropdowns(tournament_robots)
        
        print(f"Found {len(tournament_robots)} robots for tournament ID {self.current_tournament_id}")

    def update_competitor_dropdowns(self, robot_names):
        """Update the competitor dropdowns with robot names"""
        # Store current selections
        left_current = self.left_competitor_dropdown.currentText()
        right_current = self.right_competitor_dropdown.currentText()
        
        # Clear existing items
        self.left_competitor_dropdown.clear()
        self.right_competitor_dropdown.clear()
        
        # Add placeholders
        self.left_competitor_dropdown.addItem("-- Select Left Competitor --")
        self.right_competitor_dropdown.addItem("-- Select Right Competitor --")
        
        # Add robot names
        sorted_names = sorted(robot_names)
        for robot_name in sorted_names:
            self.left_competitor_dropdown.addItem(robot_name)
            self.right_competitor_dropdown.addItem(robot_name)
        
        # Restore selections if they still exist, otherwise try to restore from memory
        restored_left = False
        restored_right = False
        
        # First try to restore current selections if they exist in new list
        if left_current in sorted_names:
            self.left_competitor_dropdown.setCurrentText(left_current)
            restored_left = True
        elif self.last_left_competitor and self.last_left_competitor in sorted_names:
            # Try to restore from memory if available and valid
            self.left_competitor_dropdown.setCurrentText(self.last_left_competitor)
            restored_left = True
            print(f"Restored left competitor from memory: {self.last_left_competitor}")
        
        if right_current in sorted_names:
            self.right_competitor_dropdown.setCurrentText(right_current)
            restored_right = True
        elif self.last_right_competitor and self.last_right_competitor in sorted_names:
            # Try to restore from memory if available and valid
            self.right_competitor_dropdown.setCurrentText(self.last_right_competitor)
            restored_right = True
            print(f"Restored right competitor from memory: {self.last_right_competitor}")
        
        # If nothing was restored, set to placeholder
        if not restored_left:
            self.left_competitor_dropdown.setCurrentIndex(0)
        if not restored_right:
            self.right_competitor_dropdown.setCurrentIndex(0)
            
        # Auto-update competitor names if any were restored
        if restored_left or restored_right:
            print("Auto-updating competitor names to overlay scene")
            QTimer.singleShot(300, self.update_names)  # Slight delay to ensure UI is ready

    def on_competitor_changed(self):
        """Handle competitor selection changes - save to config"""
        # Use a timer to debounce rapid changes and avoid excessive saves
        if not hasattr(self, '_competitor_save_timer'):
            self._competitor_save_timer = QTimer()
            self._competitor_save_timer.setSingleShot(True)
            self._competitor_save_timer.timeout.connect(self.save_config)
        
        # Restart the timer each time a competitor changes
        self._competitor_save_timer.start(500)  # Save after 500ms of no changes

    def on_selection_mode_changed(self):
        """Handle manual/auto selection mode changes"""
        is_manual = self.manual_radio.isChecked()
        
        # Enable/disable manual controls based on mode
        self.left_competitor_label.setEnabled(is_manual)
        self.right_competitor_label.setEnabled(is_manual)
        self.left_competitor_dropdown.setEnabled(is_manual)
        self.right_competitor_dropdown.setEnabled(is_manual)
        # Keep name button enabled in both modes
        # self.name_button.setEnabled(is_manual)
        
        # Show/hide auto mode elements
        self.auto_match_dropdown.setVisible(not is_manual)
        self.refresh_matches_button.setVisible(not is_manual)
        
        if not is_manual:
            print("Auto mode selected - manual competitor controls disabled")
            self.load_and_auto_select_match()
            # Start auto-updating matches every 1 second
            self.auto_update_timer.start(1000)
        else:
            print("Manual mode selected - manual competitor controls enabled")
            # Stop auto-updating when in manual mode
            self.auto_update_timer.stop()

    def clear_competitor_dropdowns(self):
        """Clear competitor dropdowns when no tournament is selected"""
        self.left_competitor_dropdown.clear()
        self.right_competitor_dropdown.clear()
        self.left_competitor_dropdown.addItem("-- Select Left Competitor --")
        self.right_competitor_dropdown.addItem("-- Select Right Competitor --")

    def update_names(self):
        left = self.left_competitor_dropdown.currentText()
        right = self.right_competitor_dropdown.currentText()
        
        # Get robot data for match scene
        left_robot_data = None
        right_robot_data = None
        
        # Don't show placeholder text on overlay
        if left == "-- Select Left Competitor --":
            left = ""
        else:
            left_robot_data = self.get_robot_data_by_name(left)
            
        if right == "-- Select Right Competitor --":
            right = ""
        else:
            right_robot_data = self.get_robot_data_by_name(right)
            
        # Update both the old name boxes and the new match scene with images
        self.overlay_window.update_names(left, right)
        self.overlay_window.update_match_scene(left_robot_data, right_robot_data)
        
        # Also update fight cards scene
        self.overlay_window.update_fight_cards(left_robot_data, right_robot_data)
        
        # Also update judges scene
        self.overlay_window.update_judges(left_robot_data, right_robot_data)
        
        # Update winner scenes
        if left_robot_data:
            self.overlay_window.update_winner_red(left_robot_data)
        if right_robot_data:
            self.overlay_window.update_winner_blue(right_robot_data)

    def start_timer(self):
        if self.remaining_time <= 0:
            self.remaining_time = self.duration_input.value()
        self.is_paused = False
        self.update_timer_countdown()
        self.timer.start(1000)

    def pause_timer(self):
        if self.timer.isActive():
            self.timer.stop()
            self.is_paused = True
        elif self.is_paused:
            self.timer.start(1000)
            self.is_paused = False
        self.overlay_window.update_timer(self.remaining_time, self.is_paused)

    def set_timer_value(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Set Timer")
        form = QFormLayout(dialog)

        min_input = QSpinBox()
        min_input.setRange(0, 59)
        min_input.setValue(self.remaining_time // 60)

        sec_input = QSpinBox()
        sec_input.setRange(0, 59)
        sec_input.setValue(self.remaining_time % 60)

        form.addRow("Minutes:", min_input)
        form.addRow("Seconds:", sec_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addWidget(buttons)

        if dialog.exec():
            self.remaining_time = min_input.value() * 60 + sec_input.value()
            self.update_timer_countdown()

    def reset_timer(self):
        self.timer.stop()
        self.remaining_time = self.duration_input.value()
        self.is_paused = False
        self.update_timer_countdown()

    def update_timer_countdown(self):
        if self.remaining_time > 0:
            self.overlay_window.update_timer(self.remaining_time, self.is_paused)
            self.remaining_time -= 1
        else:
            self.overlay_window.update_timer(0, False)
            self.timer.stop()
            self.is_paused = False

    def apply_colors(self):
        self.default_bg_color = self.bg_color_input.text()
        self.left_color = self.left_color_input.text()
        self.right_color = self.right_color_input.text()
        self.default_duration = self.duration_input.value()

        self.overlay_window.update_background_color(self.default_bg_color)
        self.overlay_window.update_name_colors(self.left_color, self.right_color)
        self.save_config()

    def reset_to_defaults(self):
        self.bg_color_input.setText("#00FF00")
        self.left_color_input.setText("#C22E2E")
        self.right_color_input.setText("#2D5FCC")
        self.duration_input.setValue(120)
        self.apply_colors()

    def show_match_scene(self):
        """Switch to match scene"""
        self.overlay_window.switch_scene("match")
        
    def show_fight_cards_scene(self):
        """Switch to fight cards scene and update with current competitors"""
        left_name = self.left_competitor_dropdown.currentText()
        right_name = self.right_competitor_dropdown.currentText()
        
        # Get robot data for selected competitors
        left_robot_data = self.get_robot_data_by_name(left_name)
        right_robot_data = self.get_robot_data_by_name(right_name)
        
        print(f"Fight cards data - Left: {left_robot_data['bot_name']}, Image: {left_robot_data.get('image_url')}")
        print(f"Fight cards data - Right: {right_robot_data['bot_name']}, Image: {right_robot_data.get('image_url')}")
        
        # Switch to fight cards scene first
        self.overlay_window.switch_scene("fight-cards")
        
        # Add a small delay to ensure scene is ready before updating data
        QTimer.singleShot(150, lambda: self.overlay_window.update_fight_cards(left_robot_data, right_robot_data))
    
    def show_judges_scene(self):
        """Switch to judges scene and update with current competitors"""
        left_name = self.left_competitor_dropdown.currentText()
        right_name = self.right_competitor_dropdown.currentText()
        
        # Get robot data for selected competitors
        left_robot_data = self.get_robot_data_by_name(left_name)
        right_robot_data = self.get_robot_data_by_name(right_name)
        
        print(f"Judges scene data - Left: {left_robot_data['bot_name']}, Image: {left_robot_data.get('image_url')}")
        print(f"Judges scene data - Right: {right_robot_data['bot_name']}, Image: {right_robot_data.get('image_url')}")
        
        # Switch to judges scene first
        self.overlay_window.switch_scene("judges")
        
        # Add a small delay to ensure scene is ready before updating data
        QTimer.singleShot(150, lambda: self.overlay_window.update_judges(left_robot_data, right_robot_data))
    
    def show_rsl_scene(self):
        """Switch to RSL scene and update with current tournament data"""
        # Get current tournament data
        tournament_name = self.tournament_dropdown.currentText()
        tournament_data = None
        
        # Find tournament data from loaded tournaments
        if hasattr(self, 'tournament_data') and tournament_name in self.tournament_data:
            # Get the first tournament in the tournament_data for this name
            tournaments = self.tournament_data[tournament_name].get('tournaments', [])
            if tournaments:
                tournament_data = tournaments[0]
        
        if not tournament_data:
            # Fallback data if no tournament is found
            tournament_data = {
                'name': tournament_name,
                'description': 'Tournament Description'
            }
        
        print(f"RSL scene data - Tournament: {tournament_data.get('name')}, Description: {tournament_data.get('description')}")
        
        # Switch to RSL scene first
        self.overlay_window.switch_scene("rsl")
        
        # Add a small delay to ensure scene is ready before updating data
        QTimer.singleShot(150, lambda: self.overlay_window.update_rsl(tournament_data))
    
    def show_winner_red_scene(self):
        """Switch to winner red scene and update with left competitor"""
        left_name = self.left_competitor_dropdown.currentText()
        
        # Get robot data for left competitor (red side)
        robot_data = self.get_robot_data_by_name(left_name)
        
        print(f"Winner red scene - Robot: {robot_data['bot_name']}, Image: {robot_data.get('image_url')}")
        
        # Switch to winner red scene first
        self.overlay_window.switch_scene("winner-red")
        
        # Add a small delay to ensure scene is ready before updating data
        QTimer.singleShot(150, lambda: self.overlay_window.update_winner_red(robot_data))
    
    def show_winner_blue_scene(self):
        """Switch to winner blue scene and update with right competitor"""
        right_name = self.right_competitor_dropdown.currentText()
        
        # Get robot data for right competitor (blue side)
        robot_data = self.get_robot_data_by_name(right_name)
        
        print(f"Winner blue scene - Robot: {robot_data['bot_name']}, Image: {robot_data.get('image_url')}")
        
        # Switch to winner blue scene first
        self.overlay_window.switch_scene("winner-blue")
        
        # Add a small delay to ensure scene is ready before updating data
        QTimer.singleShot(150, lambda: self.overlay_window.update_winner_blue(robot_data))

    def show_match_queue_scene(self):
        """Switch to match queue scene and update with tournament data"""
        # Switch to match queue scene first
        self.overlay_window.switch_scene("match-queue")
        
        # Load fresh match data
        self.load_matches_data()
        
        # Get selected tournament from dropdown
        selected_tournament = self.tournament_dropdown.currentText()
        
        # Prepare match queue data with bot information
        queue_matches = []
        if self.matches_data:
            # Since load_matches_data already filters by current_tournament_id, use all matches
            sorted_matches = sorted(self.matches_data, key=lambda x: x.get('id', 0))[:10]
            
            for match in sorted_matches:
                # Get robot data for both competitors
                red_robot_id = match.get('robot_1_id')  # Fixed: was robot1_id
                blue_robot_id = match.get('robot_2_id')  # Fixed: was robot2_id
                
                red_bot_data = None
                blue_bot_data = None
                
                if red_robot_id and red_robot_id in self.robots_data:
                    red_bot_data = self.get_robot_data_for_overlay(red_robot_id)
                
                if blue_robot_id and blue_robot_id in self.robots_data:
                    blue_bot_data = self.get_robot_data_for_overlay(blue_robot_id)
                
                # Get weight class from red robot (assuming both robots are in same weight class)
                weight_class = "3lb"  # Default weight class
                if red_bot_data:
                    weight_class = red_bot_data.get('weight_class', '3lb')
                
                queue_matches.append({
                    'match_number': match.get('id', 0),
                    'red_bot': red_bot_data,
                    'blue_bot': blue_bot_data,
                    'weight_class': weight_class
                })
        
        # Get tournament data and update the scene
        tournament_data = {
            "tournament_name": getattr(self, 'current_tournament_name', 'Tournament Name'),
            "matches": queue_matches
        }
        
        # Add a small delay to ensure scene is ready before updating data
        QTimer.singleShot(150, lambda: self.overlay_window.update_match_queue(tournament_data))
    
    def refresh_match_queue_data(self):
        """Refresh match queue data for auto-update - simplified version"""
        # Only refresh if match queue scene is currently active
        try:
            # Load fresh match data
            self.load_matches_data()
            
            # Prepare match queue data with bot information
            queue_matches = []
            if self.matches_data:
                # Since load_matches_data already filters by current_tournament_id, use all matches
                sorted_matches = sorted(self.matches_data, key=lambda x: x.get('id', 0))[:10]
                
                for match in sorted_matches:
                    # Get robot data for both competitors
                    red_robot_id = match.get('robot_1_id')
                    blue_robot_id = match.get('robot_2_id')
                    
                    red_bot_data = None
                    blue_bot_data = None
                    
                    if red_robot_id and red_robot_id in self.robots_data:
                        red_bot_data = self.get_robot_data_for_overlay(red_robot_id)
                    
                    if blue_robot_id and blue_robot_id in self.robots_data:
                        blue_bot_data = self.get_robot_data_for_overlay(blue_robot_id)
                    
                    # Get weight class from red robot (assuming both robots are in same weight class)
                    weight_class = "3lb"  # Default weight class
                    if red_bot_data:
                        weight_class = red_bot_data.get('weight_class', '3lb')
                    
                    queue_matches.append({
                        'match_number': match.get('id', 0),
                        'red_bot': red_bot_data,
                        'blue_bot': blue_bot_data,
                        'weight_class': weight_class
                    })
            
            # Get tournament data and update the scene
            tournament_data = {
                "tournament_name": getattr(self, 'current_tournament_name', 'Tournament Name'),
                "matches": queue_matches
            }
            
            # Update match queue directly
            self.overlay_window.update_match_queue(tournament_data)
            print("Match queue auto-refreshed")
            
        except Exception as e:
            print(f"Error refreshing match queue data: {e}")
        
    def get_robot_data_by_name(self, robot_name):
        """Get full robot data by name including image URL"""
        if robot_name == "-- Select Left Competitor --" or robot_name == "-- Select Right Competitor --" or not robot_name:
            return {
                "bot_name": "No Robot Selected",
                "team_name": "",
                "elo": "N/A",
                "mrca_rank": None,
                "image_url": None
            }
            
        # Find robot in robots_data by bot_name
        for robot_id, robot_data in self.robots_data.items():
            if robot_data.get("bot_name") == robot_name:
                # Get robot data and add image URL from operational data
                result = robot_data.copy()
                result["image_url"] = self.get_robot_image_url(robot_id)
                return result
                
        # If not found, return default
        return {
            "bot_name": robot_name,
            "team_name": "Unknown Team",
            "elo": "N/A", 
            "mrca_rank": None,
            "image_url": None
        }

    def get_robot_image_url(self, robot_id):
        """Get image URL for a robot from operational data"""
        # Find operational record for this robot in current tournament
        print(f"Looking for image for robot_id={robot_id}, tournament_id={self.current_tournament_id}")
        
        for op_record in self.operational_data:
            if (op_record.get("robot_id") == robot_id and 
                op_record.get("tournament_id") == self.current_tournament_id):
                
                print(f"Found operational record for robot {robot_id}")
                
                # Try clean_image first, then raw_image
                clean_image = op_record.get("clean_image")
                raw_image = op_record.get("raw_image")
                
                print(f"Clean image: {clean_image}, Raw image: {raw_image}")
                
                if clean_image:
                    url = f"https://rslcheckin.replit.app{clean_image}"
                    print(f"Using clean image URL: {url}")
                    return url
                
                if raw_image:
                    url = f"https://rslcheckin.replit.app{raw_image}"
                    print(f"Using raw image URL: {url}")
                    return url
                
                # If both are null, no image available
                print(f"No image found for robot {robot_id}")
                break
        
        print(f"No operational record found for robot {robot_id} in tournament {self.current_tournament_id}")
        
        # Debug: Show what operational data we do have
        if len(self.operational_data) > 0:
            print(f"Available operational records: {len(self.operational_data)}")
            for i, record in enumerate(self.operational_data[:3]):  # Show first 3 records
                print(f"  Record {i}: robot_id={record.get('robot_id')}, tournament_id={record.get('tournament_id')}, has_clean={bool(record.get('clean_image'))}, has_raw={bool(record.get('raw_image'))}")
        else:
            print("No operational data loaded")
            
        return None

    def closeEvent(self, event):
        """Save configuration and close overlay window when the control window is closed"""
        print("Saving configuration before closing...")
        self.save_config()
        
        # Close the overlay window if it exists and is still open
        if hasattr(self, 'overlay_window') and self.overlay_window:
            print("Closing overlay window...")
            self.overlay_window.close()
        
        event.accept()

    def reopen_overlay(self):
        if not self.overlay_window.isVisible():
            self.overlay_window.show()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    control = ControlWindow()
    sys.exit(app.exec())