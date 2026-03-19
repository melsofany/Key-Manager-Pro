"""
standalone_bot.py - تشغيل البوت بدون phBot
شغّل هذا الملف مباشرة إذا لم تكن تستخدم phBot
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main_gui import main

if __name__ == "__main__":
    main()
