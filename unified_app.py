import sys
import subprocess
import threading
import warnings
from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
                             QTextEdit, QLabel, QFrame, QScrollBar, QComboBox, QCheckBox, QDesktopWidget,
                             QButtonGroup, QRadioButton)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QPalette, QColor, QFont
import hashlib
import requests
import json
import random
import jieba
from googletrans import Translator
import pyperclip
import keyboard

warnings.filterwarnings("ignore", category=DeprecationWarning)

# 注释util\client_recv_result.py 中 38-39行代码，解决重复识别问题

# 百度翻译API配置
BAIDU_APP_ID = 'xxxxxxx'
BAIDU_SECRET_KEY = 'xxxxxxxx'

# 常用语言列表，使用百度翻译 API 支持的语言代码
LANGUAGES = {
    'zh': '中文',
    'en': '英语',
    'jp': '日语',
    'kor': '韩语',
    'fra': '法语',
    'de': '德语',
    'spa': '西班牙语',
    'it': '意大利语',
    'ru': '俄语'
}

def local_translate(text, to_lang):
    translator = Translator()
    try:
        result = translator.translate(text, dest=to_lang)
        return result.text
    except Exception as e:
        print(f"本地翻译失败: {str(e)}")
        return text

def baidu_translate(query, to_lang):
    if not query.strip():
        return "空字符串，无需翻译"
    
    try:
        salt = random.randint(32768, 65536)
        sign = hashlib.md5(f"{BAIDU_APP_ID}{query}{salt}{BAIDU_SECRET_KEY}".encode()).hexdigest()
        url = 'http://api.fanyi.baidu.com/api/trans/vip/translate'
        params = {
            'q': query,
            'from': 'auto',
            'to': to_lang,
            'appid': BAIDU_APP_ID,
            'salt': salt,
            'sign': sign
        }
        response = requests.get(url, params=params)
        result = json.loads(response.text)
        if 'trans_result' in result:
            return result['trans_result'][0]['dst']
        else:
            print(f"百度翻译失败，错误信息：{result.get('error_msg', '未知错误')}")
            print("尝试本地翻译")
            return local_translate(query, to_lang)
    except Exception as e:
        print(f"百度翻译出错，尝试本地翻译: {str(e)}")
        return local_translate(query, to_lang)

class ConsoleOutput(QTextEdit):
    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.setStyleSheet("""
            background-color: #0C0C0C;
            color: #00FF00;
            border: 1px solid #00FF00;
            font-family: 'Courier New', monospace;
            font-size: 12px;
        """)
        self.verticalScrollBar().rangeChanged.connect(self.scroll_to_bottom)

    def append_text(self, text):
        self.append(f"<span style='color: #00FF00;'>{text}</span>")
        self.scroll_to_bottom()

    def scroll_to_bottom(self):
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

class HackerButton(QPushButton):
    def __init__(self, text):
        super().__init__(text)
        self.setStyleSheet("""
            QPushButton {
                background-color: #1A1A1A;
                color: #00FF00;
                border: 1px solid #00FF00;
                padding: 5px;
                font-family: 'Courier New', monospace;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00FF00;
                color: #000000;
            }
        """)

class OutputRedirector(QObject):
    output_written = pyqtSignal(str)

    def write(self, text):
        self.output_written.emit(str(text))

    def flush(self):
        pass

class ComponentWidget(QWidget):
    def __init__(self, name, command, parent=None):
        super().__init__(parent)
        self.name = name
        self.command = command
        self.process = None
        self.is_running = False
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        layout.setSpacing(10)  # 增加垂直间距

        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)  # 增加水平间距

        self.status_label = QLabel(f"{self.name} 状态: 停止")
        self.status_label.setStyleSheet("""
            color: #FF0000; 
            font-weight: bold;
            font-size: 16px;  # 增加字体大小
            padding: 5px;
        """)

        self.toggle_button = HackerButton(f"启动 {self.name}")
        self.toggle_button.setFixedSize(120, 40)  # 设置按钮固定大小
        self.toggle_button.clicked.connect(self.toggle_component)

        header_layout.addWidget(self.status_label, 1)  # 添加权重，使状态标签占据更多空间
        header_layout.addWidget(self.toggle_button)

        header_frame = QFrame()
        header_frame.setLayout(header_layout)
        header_frame.setStyleSheet("""
            background-color: #1A1A1A;
            border: 1px solid #00FF00;
            border-radius: 5px;
            padding: 10px;
        """)

        self.console = ConsoleOutput()
        self.console.setMinimumHeight(300)  # 设置控制台最小高度

        layout.addWidget(header_frame)
        layout.addWidget(self.console)

        self.setLayout(layout)

        self.output_redirector = OutputRedirector()
        self.output_redirector.output_written.connect(self.process_output)

    def process_output(self, text):
        self.console.append_text(text)
        print(f"接收到输出: {text}")  # 添加调试信息
        if '识别结果：' in text or '识别结果:' in text:
            print("检测到识别结果，尝试翻译")  # 添加调试信息
            self.parent().translate_result(text)
        else:
            print("未检测到识别结果")  # 添加调试信息

    def toggle_component(self):
        if not self.is_running:
            self.start_component()
        else:
            self.stop_component()

    def start_component(self):
        try:
            self.process = subprocess.Popen(
                self.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            self.is_running = True
            self.status_label.setText(f"{self.name} 状态: 运行中")
            self.status_label.setStyleSheet("color: #00FF00; font-weight: bold;")
            self.toggle_button.setText(f"停止 {self.name}")
            self.console.append_text(f"{self.name} 已启动...")
            threading.Thread(target=self.read_output, daemon=True).start()
        except Exception as e:
            self.console.append_text(f"启动 {self.name} 失败: {str(e)}")

    def read_output(self):
        try:
            for line in self.process.stdout:
                self.output_redirector.write(line.strip())
            self.process.wait()
            if self.process.returncode != 0:
                self.output_redirector.write(f"{self.name} 异常退出，返回码: {self.process.returncode}")
        except Exception as e:
            self.output_redirector.write(f"读取输出时发生错误: {str(e)}")
        finally:
            self.stop_component()

    def stop_component(self):
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
        self.is_running = False
        self.status_label.setText(f"{self.name} 状态: 停止")
        self.status_label.setStyleSheet("color: #FF0000; font-weight: bold;")
        self.toggle_button.setText(f"启动 {self.name}")
        self.console.append_text(f"{self.name} 已停止...")

class UnifiedApp(QWidget):
    def __init__(self):
        super().__init__()
        self.translate_enabled = True
        self.target_language = 'en'
        self.input_mode = 'recognition'  # 默认输入识别结果
        self.initUI()

    def initUI(self):
        self.setWindowTitle('CapsWriter-Pro')
        self.setGeometry(100, 100, 1300, 700)  # 增加窗口大小
        self.setStyleSheet("background-color: #0C0C0C; color: #00FF00;")
        self.center_window()

        main_layout = QVBoxLayout()
        main_layout.setSpacing(20)  # 增加主布局的间距
        main_layout.setContentsMargins(20, 20, 20, 20)  # 设置主布局的边距

        components_layout = QHBoxLayout()
        components_layout.setSpacing(20)  # 增加组件之间的间距

        # 添加翻译控件
        translate_layout = QHBoxLayout()
        translate_layout.setSpacing(10)  # 设置控件之间的间距

        self.translate_checkbox = QCheckBox("启用翻译")
        self.translate_checkbox.setStyleSheet("""
            QCheckBox {
                color: #00FF00;
                font-size: 14px;
                padding: 5px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
            }
        """)
        self.translate_checkbox.setChecked(True)
        self.translate_checkbox.stateChanged.connect(self.toggle_translation)

        language_label = QLabel("目标语言:")
        language_label.setStyleSheet("color: #00FF00; font-size: 14px; padding: 5px;")

        self.language_combo = QComboBox()
        self.language_combo.addItems(LANGUAGES.values())
        self.language_combo.setCurrentText("英语")
        self.language_combo.currentTextChanged.connect(self.change_language)
        self.language_combo.setStyleSheet("""
            QComboBox {
                background-color: #1A1A1A;
                color: #00FF00;
                border: 1px solid #00FF00;
                padding: 5px;
                font-size: 14px;
                min-width: 150px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #00FF00;
            }
            QComboBox::down-arrow {
                image: url(down_arrow.png);
                width: 14px;
                height: 14px;
            }
            QComboBox QAbstractItemView {
                background-color: #1A1A1A;
                color: #00FF00;
                selection-background-color: #00FF00;
                selection-color: #000000;
            }
        """)

        # 添加单选按钮组
        input_mode_layout = QHBoxLayout()
        self.input_mode_group = QButtonGroup(self)
        self.recognition_radio = QRadioButton("输入识别结果")
        self.translation_radio = QRadioButton("输入翻译结果")
        self.recognition_radio.setChecked(True)
        self.input_mode_group.addButton(self.recognition_radio)
        self.input_mode_group.addButton(self.translation_radio)
        self.input_mode_group.buttonClicked.connect(self.change_input_mode)

        radio_style = """
            QRadioButton {
                color: #00FF00;
                font-size: 14px;
                padding: 5px;
            }
            QRadioButton::indicator {
                width: 20px;
                height: 20px;
            }
        """
        self.recognition_radio.setStyleSheet(radio_style)
        self.translation_radio.setStyleSheet(radio_style)

        input_mode_layout.addWidget(self.recognition_radio)
        input_mode_layout.addWidget(self.translation_radio)
        input_mode_layout.addStretch(1)

        translate_layout.addWidget(self.translate_checkbox)
        translate_layout.addWidget(language_label)
        translate_layout.addWidget(self.language_combo)
        translate_layout.addLayout(input_mode_layout)
        translate_layout.addStretch(1)  # 添加弹性空间

        # 直接运行 .exe 文件
        self.client_widget = ComponentWidget("客户端", ["start_client.exe"], self)
        self.server_widget = ComponentWidget("服务端", ["start_server.exe"], self)

        components_layout.addWidget(self.client_widget)
        components_layout.addWidget(self.server_widget)

        main_layout.addLayout(translate_layout)
        main_layout.addLayout(components_layout)

        self.setLayout(main_layout)

        # 添加动画效果
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.animate_border)
        self.animation_timer.start(1000)  # 每秒更新一次

    def toggle_translation(self, state):
        self.translate_enabled = state == Qt.Checked
        print(f"翻译功能已{'启用' if self.translate_enabled else '禁用'}")  # 添加调试信息

    def change_language(self, language):
        self.target_language = list(LANGUAGES.keys())[list(LANGUAGES.values()).index(language)]
        print(f"目标语言已更改为: {self.target_language}")  # 添加调试信息

    def change_input_mode(self, button):
        self.input_mode = 'recognition' if button == self.recognition_radio else 'translation'
        print(f"输入模式已更改为: {'识别结果' if self.input_mode == 'recognition' else '翻译结果'}")

    def translate_result(self, text):
        if self.translate_enabled:
            result = text.split('识别结果：')[-1].strip() if '识别结果：' in text else text.split('识别结果:')[-1].strip()
            if not result:
                return
            try:
                translated = baidu_translate(result, self.target_language)
                translated_text = f"翻译结果 ({LANGUAGES[self.target_language]}): {translated}"
                self.client_widget.console.append_text(translated_text)
                self.server_widget.console.append_text(translated_text)
                
                # 根据选择的输入模式决定输入内容
                input_text = result if self.input_mode == 'recognition' else translated
                self.input_to_cursor(input_text)
            except Exception as e:
                error_message = f"翻译过程中出错: {str(e)}"
                print(error_message)
                self.client_widget.console.append_text(error_message)
                self.server_widget.console.append_text(error_message)
        else:
            print("翻译未启用")

    def input_to_cursor(self, text):
        pyperclip.copy(text)
        keyboard.press_and_release('ctrl+v')

    def animate_border(self):
        border_color = QColor(0, 255, 0) if self.property("border_green") else QColor(0, 200, 0)
        self.setStyleSheet(f"""
            background-color: #0C0C0C;
            color: #00FF00;
            border: 2px solid {border_color.name()};
        """)
        self.setProperty("border_green", not self.property("border_green"))

    def center_window(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # 设置深色主题
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(12, 12, 12))
    palette.setColor(QPalette.WindowText, QColor(0, 255, 0))
    palette.setColor(QPalette.Base, QColor(15, 15, 15))
    palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ToolTipBase, QColor(0, 255, 0))
    palette.setColor(QPalette.ToolTipText, QColor(0, 0, 0))
    palette.setColor(QPalette.Text, QColor(0, 255, 0))
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ButtonText, QColor(0, 255, 0))
    palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.Highlight, QColor(0, 255, 0).lighter())
    palette.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
    app.setPalette(palette)

    ex = UnifiedApp()
    ex.show()
    sys.exit(app.exec_())
