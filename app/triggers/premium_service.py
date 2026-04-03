"""
Compatibility shim.

Pricing logic moved to `app.services.pricing_service` so pricing lives with other services.
"""

from app.services.pricing_service import PricingService as PremiumService
