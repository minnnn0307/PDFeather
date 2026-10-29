import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys,tempfile,unittest
from pathlib import Path
from contextlib import ExitStack
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Qt,QSettings,QPoint,QPointF,QRectF
from PySide6.QtGui import QImage,QColor
from PySide6.QtWidgets import QApplication,QDialog
from PySide6.QtTest import QTest
from main import Window
from preferences import Preferences
from capture import CaptureCollection,snapshot
from scripts.smoke_fixture import create_pdf

app=QApplication.instance() or QApplication([])
app.setProperty('offlineTests',True)

def settle():
    for _ in range(5): app.processEvents()

def make_window(temp):
    return Window(Preferences(QSettings(str(Path(temp)/'settings.ini'),QSettings.Format.IniFormat)))

class InteractionTests(unittest.TestCase):
    def test_titlebar_drag_maximize_and_restore(self):
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QMouseEvent
        with tempfile.TemporaryDirectory() as temp:
            window=make_window(temp); window.show(); settle()
            try:
                bar=window.titlebar; screen=window.screen().availableGeometry()
                normal_size=window.size()
                def send(target,kind,point,buttons):
                    local=target.mapFromGlobal(point)
                    event=QMouseEvent(kind,QPointF(local),QPointF(point),
                        Qt.MouseButton.NoButton if kind==QEvent.Type.MouseMove else Qt.MouseButton.LeftButton,
                        buttons,Qt.KeyboardModifier.NoModifier)
                    QApplication.sendEvent(target,event); settle()
                start=bar.mapToGlobal(QPoint(100,20))
                top=QPoint(screen.center().x(),screen.top())
                send(bar,QEvent.Type.MouseButtonPress,start,Qt.MouseButton.LeftButton)
                send(bar,QEvent.Type.MouseMove,top,Qt.MouseButton.LeftButton)
                send(bar,QEvent.Type.MouseButtonRelease,top,Qt.MouseButton.NoButton)
                self.assertTrue(window.isMaximized()); self.assertEqual(bar.max_button.property('iconName'),'restore')
                start=bar.mapToGlobal(QPoint(100,20)); end=start+QPoint(40,140)
                send(bar,QEvent.Type.MouseButtonPress,start,Qt.MouseButton.LeftButton)
                send(bar,QEvent.Type.MouseMove,end,Qt.MouseButton.LeftButton)
                send(bar,QEvent.Type.MouseButtonRelease,end,Qt.MouseButton.NoButton)
                self.assertFalse(window.isMaximized()); self.assertEqual(window.size(),normal_size)
                self.assertEqual(bar.max_button.property('iconName'),'maximize')
                self.assertLess(abs(window.mapFromGlobal(end).y()-20),2)
                # A click alone must not restore a maximized window.
                window.showMaximized(); settle(); start=bar.mapToGlobal(QPoint(100,20))
                send(bar,QEvent.Type.MouseButtonPress,start,Qt.MouseButton.LeftButton)
                send(bar,QEvent.Type.MouseButtonRelease,start,Qt.MouseButton.NoButton)
                self.assertTrue(window.isMaximized())
            finally: window.close_all()

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
            window=make_window(temp); cleanup.callback(window.close_all); window.open(str(source)); window.show(); settle()
            def char_point(index):
                rect=window.canvas.rects[0][1]; page=window.doc.pdf[0]; text=page.get_textpage()
                try: l,b,r,t=text.get_charbox(index)
                finally: text.close(); page.close()
                return QPoint(round(rect.x()+(l+r)/2*window.zoom),round(rect.y()+(842-(b+t)/2)*window.zoom))
            window.set_selection_tool('text')
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
            window.close_all()

    def test_pointer_hand_and_integrated_title_tabs(self):
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtCore import QEvent
        with tempfile.TemporaryDirectory() as temp, ExitStack() as cleanup:
            source=Path(temp)/'input.pdf'; create_pdf(source,4)
            window=make_window(temp); cleanup.callback(window.close_all); window.open(str(source)); window.show(); settle()
            self.assertIs(window.file_tabs.parentWidget(),window.titlebar)
            self.assertEqual(window.titlebar.title.text(),'PDFeather')
            window.set_selection_tool('pointer'); start=QPoint(400,200); end=QPoint(450,260)
            QTest.mousePress(window.canvas,Qt.MouseButton.LeftButton,pos=start); QTest.mouseMove(window.canvas,end); QTest.mouseRelease(window.canvas,Qt.MouseButton.LeftButton,pos=end)
            self.assertIsNone(window.selection.anchor); self.assertFalse(window.captures.items); self.assertIsNone(window.canvas.capture_rect)
            window.set_zoom(2); settle(); window.scroll.verticalScrollBar().setValue(300); window.scroll.horizontalScrollBar().setValue(100)
            window.set_selection_tool('hand')
            anchor=QPointF(400,400); global_anchor=QPointF(window.canvas.mapToGlobal(QPoint(400,400)))
            def send(kind,local,global_point,button,buttons):
                QApplication.sendEvent(window.canvas,QMouseEvent(kind,local,global_point,button,buttons,Qt.KeyboardModifier.NoModifier))
            send(QEvent.Type.MouseButtonPress,anchor,global_anchor,Qt.MouseButton.LeftButton,Qt.MouseButton.LeftButton)
            send(QEvent.Type.MouseMove,anchor-QPointF(40,60),global_anchor-QPointF(40,60),Qt.MouseButton.NoButton,Qt.MouseButton.LeftButton)
            send(QEvent.Type.MouseButtonRelease,anchor-QPointF(40,60),global_anchor-QPointF(40,60),Qt.MouseButton.LeftButton,Qt.MouseButton.NoButton)
            self.assertEqual(window.scroll.verticalScrollBar().value(),360); self.assertEqual(window.scroll.horizontalScrollBar().value(),140)
            self.assertFalse(window.captures.items); self.assertEqual(window.canvas.cursor().shape(),Qt.CursorShape.OpenHandCursor)
            changes=[]; window.mode.currentIndexChanged.connect(changes.append); window.mode.actions[2].trigger(); self.assertEqual(window.mode.currentIndex(),2); self.assertEqual(changes[-1],2)
            close=window.file_tabs.tabButton(0,window.file_tabs.ButtonPosition.RightSide); QTest.mouseClick(close,Qt.MouseButton.LeftButton); settle(); self.assertIsNone(window.doc)
            window.close_all()

    def test_external_files_wait_for_modal_and_reuse_window(self):
        with tempfile.TemporaryDirectory() as temp, ExitStack() as cleanup:
            first=Path(temp)/'first.pdf'; second=Path(temp)/'second.pdf'; create_pdf(first,2); create_pdf(second,3)
            window=make_window(temp); cleanup.callback(window.close_all); window.open(str(first)); window.show(); settle()
            dialog=QDialog(window); dialog.setModal(True); dialog.show(); cleanup.callback(dialog.close); settle()
            window.receive_external_files([str(second)]); settle(); self.assertEqual(window.file_tabs.count(),1)
            dialog.close(); QTest.qWait(200); settle(); self.assertEqual(window.file_tabs.count(),2); self.assertEqual(Path(window.doc.path).name,'second.pdf')
            window.receive_external_files([str(second)]); settle(); self.assertEqual(window.file_tabs.count(),2)
            window.close_all()

    def test_tabs_restore_view_search_selection_and_release_cache(self):
        with tempfile.TemporaryDirectory() as temp, ExitStack() as cleanup:
            first=Path(temp)/'first.pdf'; second=Path(temp)/'second.pdf'; create_pdf(first,5); create_pdf(second,2)
            window=make_window(temp); cleanup.callback(window.close_all); window.open(str(first)); window.show(); settle()
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
            window.close_all()

if __name__=='__main__': unittest.main()
