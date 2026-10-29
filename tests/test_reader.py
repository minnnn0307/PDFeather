import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from layout import parse_pages, placement, grid, print_cells, print_placement
from preferences import Preferences
from app_meta import VERSION
from PySide6.QtCore import QSettings
from scripts.smoke_fixture import create_pdf
from PySide6.QtWidgets import QApplication
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtGui import QPainter, QPageSize
from main import Document, Window, PrintWindow

app = QApplication.instance() or QApplication([])
app.setProperty('offlineTests',True)

class Tests(unittest.TestCase):
    def test_single_page_scroll_center_and_1000_percent(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'single.pdf'; create_pdf(path,1)
            prefs=Preferences(QSettings(str(Path(temp)/'settings.ini'),QSettings.Format.IniFormat))
            window=Window(prefs); window.show()
            try:
                window.open(str(path))
                for mode in (1,3):
                    window.mode.setCurrentIndex(mode); window.set_zoom(.3)
                    for _ in range(8): app.processEvents()
                    rect=window.canvas.rects[0][1]
                    viewport=window.scroll.viewport()
                    self.assertAlmostEqual(rect.center().x(),viewport.width()/2,delta=1)
                    self.assertAlmostEqual(rect.center().y(),viewport.height()/2,delta=1)
                window.zoom_box.setValue(1000)
                for _ in range(8): app.processEvents()
                self.assertEqual(window.zoom,10.)
                window.close_current_tab(); window.open(str(path))
                for _ in range(8): app.processEvents()
                self.assertEqual(window.zoom,10.)
                window.set_zoom(12.)
                self.assertEqual(window.zoom,10.)
            finally: window.close_all()

    def test_ranges(self):
        self.assertEqual(parse_pages('1-3,5,2', 5), [0,1,2,4])
        self.assertEqual(parse_pages('', 2), [0,1])
        for value in ('0', '4', '3-1', 'a', '1-', '1,,2'):
            with self.assertRaises(ValueError): parse_pages(value, 3)

    def test_layout(self):
        self.assertEqual(placement((100,200),(0,0,400,400),72), (100,0,200,400))
        self.assertEqual(placement((100,200),(0,0,400,400),72,100), (150,100,100,200))
        for n in (1,2,4,6,9,16):
            cols, rows = grid(n); self.assertEqual(cols*rows,n)

    def test_tile_rendering_and_dpi(self):
        from rendering import visible_tiles
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QImage
        with tempfile.TemporaryDirectory() as temp:
            source=str(Path(temp)/'input.pdf'); create_pdf(source,1)
            doc=Document(source)
            try:
                reference=doc.image(0,2,cached=False)
                stitched=QImage(reference.size(),QImage.Format.Format_RGB888); stitched.fill(0)
                painter=QPainter(stitched)
                rect=QRectF(0,0,1190,1684)
                for tile,target in visible_tiles(rect,rect,1):
                    image=doc.tile(0,*tile); painter.drawImage(target,image)
                    self.assertLessEqual(image.width()*image.height(),768*768)
                painter.end()
                actual_rgba=stitched.convertToFormat(QImage.Format.Format_RGBA8888); reference_rgba=reference.convertToFormat(QImage.Format.Format_RGBA8888)
                self.assertTrue(actual_rgba==reference_rgba,'Tiled rendering differs from the full-resolution reference')
                # At 1000% and 2x DPR a full page would exceed 200 MP; only visible tiles are allocated.
                page_rect=QRectF(0,0,5950,8420); visible=QRectF(500,300,900,650)
                tiles=list(visible_tiles(page_rect,visible,2))
                self.assertTrue(tiles); self.assertEqual(tiles[0][0][:2],(11900,16840))
                pixels=0
                for tile,_ in tiles:
                    image=doc.tile(0,*tile); pixels+=image.width()*image.height()
                self.assertLess(pixels,11900*16840/4)
                self.assertLessEqual(doc.cache_bytes,64*1024*1024)
            finally: doc.close()

    def test_fit_relative_print_scale(self):
        fit=print_placement((100,200),(0,0,400,400),72,100,'fit')
        self.assertEqual(fit,(100,0,200,400))
        self.assertEqual(print_placement((100,200),(0,0,400,400),72,50,'fit'),(150,100,100,200))
        self.assertEqual(print_placement((100,200),(0,0,400,400),72,100,'actual'),(150,100,100,200))

    def test_print_margins(self):
        cells=print_cells((210,297),(10,20,30,40),4,2,25.4)
        self.assertEqual(cells[0],(10,20,84,117.5))
        self.assertEqual(cells[3],(96,139.5,84,117.5))
        self.assertEqual(print_cells((210,297),(0,0,0,0),1,0,25.4),[(0,0,210,297)])
        for margins,gap in [((120,0,120,0),0),((0,150,0,150),0),((0,0,0,0),300)]:
            with self.assertRaises(ValueError): print_cells((210,297),margins,4,gap,72)
        # Verify white physical margins around a PDF filled all the way to its edges.
        with tempfile.TemporaryDirectory() as temp:
            from scripts.smoke_fixture import create_pdf
            source=str(Path(temp)/'solid.pdf')
            create_pdf(source,1,background=True)
            from printing import make_printer,paint_document
            doc=Document(source)
            settings=dict(path=source,selected=[0],nup=1,percent=None,paper='A4',landscape=False,duplex=0,copies=1,device='',sheet=0,margins=[20,20,20,20],gap=0)
            output=str(Path(temp)/'margins.pdf'); printer=make_printer(settings,output)
            paint_document(doc,printer,settings); doc.close()
            output_doc=Document(output); image=output_doc.image(0,1,cached=False)
            self.assertGreater(image.pixelColor(15,image.height()//2).red(),245)
            self.assertLess(image.pixelColor(image.width()//2,image.height()//2).red(),100)
            self.assertGreater(image.pixelColor(image.width()-15,image.height()//2).red(),245)
            output_doc.close()

    def test_preferences_and_centering(self):
        with tempfile.TemporaryDirectory() as temp, ExitStack() as cleanup:
            source=str(Path(temp)/'input.pdf'); create_pdf(source,3)
            settings_path=str(Path(temp)/'preferences.ini')
            prefs=Preferences(QSettings(settings_path,QSettings.Format.IniFormat))
            window=Window(prefs); cleanup.callback(window.close_all); window.open(source); window.show(); app.processEvents()
            panel=window.settings_panel
            panel.controls['theme'].setCurrentIndex(panel.controls['theme'].findData('light'))
            self.assertEqual(window.theme_name,'light')
            self.assertNotIn(VERSION,window.windowTitle())
            panel.controls['render_mode'].setCurrentIndex(panel.controls['render_mode'].findData('page'))
            self.assertEqual(prefs.get('render_mode'),'page')
            panel.controls['render_mode'].setCurrentIndex(panel.controls['render_mode'].findData('tiles'))
            self.assertEqual(Preferences(QSettings(settings_path,QSettings.Format.IniFormat)).get('theme'),'light')
            panel.controls['default_mode'].setCurrentIndex(0)
            window.set_zoom(.4)
            for _ in range(3): app.processEvents()
            viewport=window.scroll.viewport().rect(); rect=window.canvas.rects[0][1]
            self.assertAlmostEqual(rect.center().x(),viewport.width()/2,delta=1)
            self.assertAlmostEqual(rect.center().y(),viewport.height()/2,delta=1)
            window.mode.setCurrentIndex(2); window.set_zoom(.3)
            for _ in range(3): app.processEvents()
            rect=window.canvas.rects[0][1].united(window.canvas.rects[1][1])
            self.assertAlmostEqual(rect.center().x(),window.scroll.viewport().width()/2,delta=1)
            self.assertAlmostEqual(rect.center().y(),window.scroll.viewport().height()/2,delta=1)
            window.mode.setCurrentIndex(1); self.assertEqual(window.canvas.rects[0][1].top(),0)
            panel.controls['margin_left'].setValue(23.5)
            self.assertEqual(Preferences(QSettings(settings_path,QSettings.Format.IniFormat)).get('margin_left'),23.5)
            panel.controls['theme'].setCurrentIndex(panel.controls['theme'].findData('dark'))
            self.assertEqual(window.theme_name,'dark')
            from branding import application_icon
            self.assertFalse(application_icon().isNull())
            window.close_all()

    def test_document_modes_and_print(self):
        with tempfile.TemporaryDirectory() as temp, ExitStack() as cleanup:
            source = str(Path(temp)/'input.pdf')
            create_pdf(source,5)
            window = Window(Preferences(QSettings(str(Path(temp)/'preferences.ini'),QSettings.Format.IniFormat))); cleanup.callback(window.close_all); window.open(source)
            self.assertEqual(len(window.doc.sizes), 5)
            image = window.doc.image(0,1)
            self.assertFalse(image.isNull())
            for mode, count in ((0,1),(1,5),(2,2),(3,5)):
                window.mode.setCurrentIndex(mode); window.go(0)
                self.assertEqual(len(window.canvas.rects),count)
            window.set_zoom(1.5); self.assertEqual(window.zoom,1.5)
            from printing import make_printer, paint_document
            settings=dict(path=source,selected=list(range(5)),nup=2,percent=None,paper='A4',landscape=False,duplex=0,copies=1,device='',sheet=0)
            output=str(Path(temp)/'output.pdf')
            output_printer=make_printer(settings,output)
            paint_document(window.doc,output_printer,settings)
            result=Document(output)
            self.assertEqual(len(result.sizes),3); result.close()
            window.show(); app.processEvents()
            window.mode.setCurrentIndex(1); window.set_zoom(2.0)
            window.scroll.horizontalScrollBar().setValue(100)
            window.scroll.verticalScrollBar().setValue(300)
            from PySide6.QtCore import QPoint, QPointF, Qt, QTimer
            anchor=QPoint(250,220)
            before=window.canvas.mapFrom(window.scroll.viewport(),anchor)
            old_rect=window.canvas.rects[0][1]
            pdf_point=((before.x()-old_rect.x())/window.zoom,(before.y()-old_rect.y())/window.zoom)
            window.set_zoom(2.3,anchor)
            after=window.canvas.mapFrom(window.scroll.viewport(),anchor); rect=window.canvas.rects[0][1]
            self.assertAlmostEqual((after.x()-rect.x())/window.zoom,pdf_point[0],delta=1)
            self.assertAlmostEqual((after.y()-rect.y())/window.zoom,pdf_point[1],delta=1)
            window.mode.setCurrentIndex(0); window.go(0)
            window.scroll.verticalScrollBar().setValue(window.scroll.verticalScrollBar().maximum())
            from PySide6.QtGui import QWheelEvent
            event=QWheelEvent(QPointF(100,100),QPointF(window.scroll.viewport().mapToGlobal(QPoint(100,100))),QPoint(),QPoint(0,-120),Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.NoScrollPhase,False)
            QApplication.sendEvent(window.scroll.viewport(),event)
            self.assertEqual(window.current,1)
            window.show_search(); window.search_input.setText('Page'); window.search_debounce.stop(); window.begin_search()
            for _ in range(6): window.search_step()
            self.assertEqual(len(window.matches),5,window.search_status.text())
            window.next_match(1); self.assertEqual(window.match_index,1)
            # The print dialog must return immediately and keep its event loop alive.
            import time
            started=time.monotonic(); dialog=PrintWindow(window.doc,window); cleanup.callback(dialog.close); dialog.show()
            self.assertLess(time.monotonic()-started,3)
            ticks=[]; heartbeat=QTimer(); heartbeat.setInterval(5); heartbeat.timeout.connect(lambda:ticks.append(1)); heartbeat.start()
            deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                app.processEvents(); time.sleep(.01)
                if dialog.preview_label.pixmap() and not dialog.preview_label.pixmap().isNull(): break
            heartbeat.stop()
            self.assertFalse(dialog.scale.isEnabled()); self.assertEqual(dialog.scale.value(),100)
            dialog.scale_mode.setCurrentIndex(2); dialog.scale.setValue(75)
            self.assertTrue(dialog.scale.isEnabled()); self.assertEqual(dialog.settings()['percent'],75); self.assertEqual(dialog.settings()['scale_basis'],'fit')
            dialog.set_busy(True); self.assertFalse(dialog.scale.isEnabled()); dialog.set_busy(False); self.assertTrue(dialog.scale.isEnabled())
            dialog.scale_mode.setCurrentIndex(0); self.assertFalse(dialog.scale.isEnabled()); self.assertEqual(dialog.scale.value(),100)
            dialog.scale_mode.setCurrentIndex(1); self.assertFalse(dialog.scale.isEnabled()); self.assertEqual(dialog.settings()['scale_basis'],'actual')
            self.assertGreater(len(ticks),3)
            self.assertTrue(dialog.preview_label.pixmap() and not dialog.preview_label.pixmap().isNull(),dialog.error.text())
            dialog.close(); window.close_all()

if __name__ == '__main__': unittest.main()
