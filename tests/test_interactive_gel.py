import unittest
import os
import urllib.request
from biolabcalc.interactive_gel import (
    get_interactive_html,
    save_interactive_app,
    calculate_ladder_standard_curve,
    estimate_band_mw,
    launch_interactive_annotator,
)

class TestInteractiveGel(unittest.TestCase):
    def test_get_interactive_html(self):
        html = get_interactive_html()
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("gelCanvas", html)
        self.assertIn("Drag & Drop", html)
        self.assertIn("interpolateMwFromRf", html)

    def test_save_interactive_app(self):
        out_path = "/tmp/test_save_gel_app.html"
        res = save_interactive_app(out_path)
        self.assertTrue(os.path.exists(res))
        self.assertGreater(os.path.getsize(res), 5000)
        os.remove(out_path)

    def test_calculate_ladder_standard_curve(self):
        # Sample ladder bands: 10000 bp at Rf 0.1, 1000 bp at Rf 0.5, 100 bp at Rf 0.9
        # log10: 4.0, 3.0, 2.0
        calibration_points = [(10000, 0.1), (1000, 0.5), (100, 0.9)]
        slope, intercept, r2 = calculate_ladder_standard_curve(calibration_points)
        # log10(MW) = -2.5 * Rf + 4.25
        self.assertAlmostEqual(slope, -2.5, delta=0.1)
        self.assertAlmostEqual(r2, 1.0, delta=0.01)

        # Estimate MW at Rf = 0.5 -> should be 1000 bp
        est_mw = estimate_band_mw(0.5, slope, intercept)
        self.assertAlmostEqual(est_mw, 1000.0, delta=50.0)

    def test_launch_server(self):
        # Test background server launch
        url = launch_interactive_annotator(port=0, open_browser=False, blocking=False)
        self.assertIn("http://127.0.0.1:", url)
        # Test GET request
        with urllib.request.urlopen(url) as response:
            self.assertEqual(response.status, 200)
            content = response.read().decode("utf-8")
            self.assertIn("gelCanvas", content)

if __name__ == '__main__':
    unittest.main()
