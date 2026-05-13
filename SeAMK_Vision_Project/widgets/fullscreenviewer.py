from PySide6.QtWidgets import QDialog, QVBoxLayout, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QImage, QPainter
from PySide6.QtOpenGLWidgets import QOpenGLWidget

class FullscreenViewer(QDialog):
    def __init__(self, parent=None, title=""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.Window | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)
        
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.pixmap_item = QGraphicsPixmapItem()
        
        self.is_interacting = False
        self.interaction_timer = QTimer(self)
        self.interaction_timer.setSingleShot(True)
        self.interaction_timer.timeout.connect(self.end_interaction)

        self._init_ui_settings()
        self._setup_layout()

    def _init_ui_settings(self):
        self.view.setViewport(QOpenGLWidget())
        self.view.setViewportUpdateMode(QGraphicsView.SmartViewportUpdate)
        self.view.setRenderHint(QPainter.Antialiasing, False)
        self.view.setRenderHint(QPainter.SmoothPixmapTransform, False)
        
        self.pixmap_item.setTransformationMode(Qt.FastTransformation)
        self.scene.addItem(self.pixmap_item)
        
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.resize(1200, 900)

    def _setup_layout(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)

    def end_interaction(self):
        self.is_interacting = False

    def update_image(self, image_data):
        if not self.isVisible() or self.is_interacting:
            return

        try:
            if hasattr(image_data, 'shape'):
                h, w, ch = image_data.shape
                q_img = QImage(image_data.data, w, h, ch * w, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(q_img, Qt.NoFormatConversion)
            else:
                pixmap = QPixmap.fromImage(image_data)

            self.pixmap_item.setPixmap(pixmap)
            
            if not hasattr(self, '_initial_fit'):
                self.view.fitInView(self.pixmap_item, Qt.KeepAspectRatio)
                self._initial_fit = True
                
        except Exception as e:
            print(f"Viewer Error: {e}")

    def mousePressEvent(self, event):
        self.is_interacting = True
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.interaction_timer.start(300)
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        self.is_interacting = True
        self.interaction_timer.start(300)
        factor = 1.15 if event.angleDelta().y() > 0 else 0.85
        self.view.scale(factor, factor)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
        elif event.key() == Qt.Key_Escape:
            self.close()