import warnings
warnings.filterwarnings("ignore")  # Catches all warnings

# ReportLab specific config
from reportlab import rl_config
rl_config.warnOnMissingFontGlyphs = 0
rl_config.verbose = 0

# Now import ReportLab components
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas