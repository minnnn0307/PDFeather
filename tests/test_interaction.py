import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys,tempfile,unittest
from pathlib import Path
from contextlib import ExitStack
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Qt,QSettings,QPoint,QPointF,QRectF
from PySide6.QtGui import QImage,QColor
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from main import Window
from preferences import Preferences
from capture import CaptureCollection,snapshot
from scripts.smoke_fixture import create_pdf

app=QApplication.instance() or QApplication([])

def settle():
    for _ in range(5): app.processEvents()

def make_window(temp):
    return Window(Preferences(QSettings(str(Path(temp)/'settings.ini'),QSettings.Format.IniFormat)))

class InteractionTests(unittest.TestCase):
    def test_stacking_order_padding_undo_and_limit(self):
        collection=CaptureCollection(limit=200)
        try:
            top=QImage(6,4,QImage.Format.Format_RGB888); top.fill(QColor('red'))
            bottom=QImage(10,3,QImage.Format.Format_RGB888); bottom.fill(QColor('blue'))
            collection.add(top); collection.add(bottom)
            merged=collection.image()
            self.assertEqual(merged.size().width(),10); self.assertEqual(merged.size().height(),7)
            self.assertEqual(merged.pixelColor(3,1),QColor('red')); self.assertEqual(merged.pixelColor(0,1),QColor('white')); self.assertEqual(merged.pixelColor(3,5),QColor('blue'))
            huge=QImage(30,30,QImage.Format.Format_RGB888)
            with self.assertRaises(ValueError): collection.add(huge)
            self.assertEqual(len(collection.items),2)
            old=collection.items[-1][0]; collection.undo(); self.assertFalse(old.exists()); self.assertEqual(collection.size,(6,4))
            collection.clear(); self.assertEqual(collection.size,(0,0))
        finally: collection.close()

    def test_text_drag_clipboard_and_two_capture_modes(self):
        with tempfile.TemporaryDirectory() as temp, ExitStack() as cleanup:
            source=Path(temp)/'input.pdf'; create_pdf(source,3)
            window=make_window(temp); cleanup.callback(window.close); window.open(str(source)); window.show(); settle()
            def char_point(index):
                rect=window.canvas.rects[0][1]; page=window.doc.pdf[0]; text=page.get_textpage()
                try: l,b,r,t=text.get_charbox(index)
                finally: text.close(); page.close()
                return QPoint(round(rect.x()+(l+r)/2*window.zoom),round(rect.y()+(842-(b+t)/2)*window.zoom))
            start,end=char_point(0),char_point(3)
            self.assertEqual(window.selection.hit(QPointF(start),window.canvas.rects,True),(0,0))
            QTest.mousePress(window.canvas,Qt.MouseButton.LeftButton,pos=start); QTest.mouseMove(window.canvas,end); QTest.mouseRelease(window.canvas,Qt.MouseButton.LeftButton,pos=end)
            self.assertEqual(window.selection.text(),'Page')
            QTest.keyClick(window.canvas,Qt.Key.Key_C,Qt.KeyboardModifier.ControlModifier)
            self.assertEqual(QApplication.clipboard().text(),'Page')
            # Reversed dragging and selection across pages preserve text order.
            window.selection.begin((1,3)); window.selection.extend((0,0))
            text=window.selection.text(); self.assertTrue(text.startswith('Page 1')); self.assertTrue(text.endswith('Page'))
            window.set_selection_tool('capture'); settle()
            rect=window.canvas.rects[0][1]
            region=QRectF(rect.x()+20,rect.y()+40,180,90)
            QTest.mousePress(window.canvas,Qt.MouseButton.LeftButton,pos=region.topLeft().toPoint()); QTest.mouseMove(window.canvas,region.bottomRight().toPoint()); QTest.mouseRelease(window.canvas,Qt.MouseButton.LeftButton,pos=region.bottomRight().toPoint())
            clipboard=QApplication.clipboard().image(); self.assertFalse(clipboard.isNull()); self.assertEqual(clipboard.width(),round(180*window.canvas.devicePixelRatioF()))
            window.set_selection_tool('multi'); settle()
            rect=window.canvas.rects[0][1]; first=QRectF(rect.x()+20,rect.y()+40,180,90)
            def drag_capture(region):
                QTest.mousePress(window.canvas,Qt.MouseButton.LeftButton,pos=region.topLeft().toPoint()); QTest.mouseMove(window.canvas,region.bottomRight().toPoint()); QTest.mouseRelease(window.canvas,Qt.MouseButton.LeftButton,pos=region.bottomRight().toPoint())
            drag_capture(first); self.assertEqual(len(window.captures.items),1)
            rect=next(r for i,r in window.canvas.rects if i==1)
            window.scroll.verticalScrollBar().setValue(round(rect.top())); settle()
            self.assertEqual(window.current,1)
            rect=next(r for i,r in window.canvas.rects if i==1)
            drag_capture(QRectF(rect.x()+10,rect.y()+35,220,70)); self.assertEqual(len(window.captures.items),2)
            window.copy_captures(); copied=QApplication.clipboard().image()
            self.assertEqual(copied.width(),round(220*window.canvas.devicePixelRatioF())); self.assertEqual(copied.height(),round(160*window.canvas.devicePixelRatioF()))
            window.undo_capture(); self.assertEqual(len(window.captures.items),1); window.clear_captures(); self.assertFalse(window.captures.items)
            window.close()

    def test_tabs_restore_view_search_selection_and_release_cache(self):
        with tempfile.TemporaryDirectory() as temp, ExitStack() as cleanup:
            first=Path(temp)/'first.pdf'; second=Path(temp)/'second.pdf'; create_pdf(first,5); create_pdf(second,2)
            window=make_window(temp); cleanup.callback(window.close); window.open(str(first)); window.show(); settle()
            first_doc=window.doc; window.mode.setCurrentIndex(1); window.set_zoom(1.5); window.go(2); settle()
            window.selection.begin((2,0)); window.selection.extend((2,3)); scroll=window.scroll.verticalScrollBar().value()
            window.show_search(); window.search_input.setText('Page'); window.search_debounce.stop(); window.begin_search()
            for _ in range(6): window.search_step()
            window.go(2); scroll=window.scroll.verticalScrollBar().value()
            window.open(str(second)); settle()
            self.assertEqual(window.file_tabs.count(),2); self.assertEqual(first_doc.cache_bytes,0)
            window.mode.setCurrentIndex(0); window.set_zoom(.7); window.go(1); settle()
            window.file_tabs.setCurrentIndex(0); settle()
            self.assertIs(window.doc,first_doc); self.assertEqual(window.current,2); self.assertEqual(window.mode.currentIndex(),1); self.assertEqual(window.zoom,1.5)
            self.assertAlmostEqual(window.scroll.verticalScrollBar().value(),scroll,delta=2)
            self.assertEqual(window.selection.text(),'Page'); self.assertEqual(window.search_input.text(),'Page'); self.assertEqual(len(window.matches),5)
            self.assertLessEqual(sum(window.file_tabs.tabData(i).doc.cache_bytes for i in range(window.file_tabs.count())),64*1024*1024)
            # Opening an existing path activates it instead of adding a duplicate.
            window.open(str(second)); settle(); self.assertEqual(window.file_tabs.count(),2); self.assertEqual(window.current,1); self.assertEqual(window.zoom,.7)
            # Tab moves keep the document state attached to the tab.
            window.file_tabs.moveTab(1,0); settle(); self.assertEqual(Path(window.doc.path).name,'second.pdf')
            window.close_current_tab(); settle(); self.assertEqual(window.file_tabs.count(),1); self.assertIs(window.doc,first_doc)
            window.close_current_tab(); settle(); self.assertIsNone(window.doc); self.assertEqual(window.file_tabs.count(),0)
            window.open(str(first)); settle(); self.assertIsNotNone(window.doc)
            window.close()

if __name__=='__main__': unittest.main()
