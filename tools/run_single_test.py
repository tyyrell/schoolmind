import unittest
from run_tests import SchoolMindAITest

if __name__ == '__main__':
    suite = unittest.TestSuite()
    suite.addTest(SchoolMindAITest('test_homepage_arabic_copy_is_translated_not_only_rtl'))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
