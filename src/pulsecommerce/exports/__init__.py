"""Export layer: flattens the warehouse for external BI tools."""

from pulsecommerce.exports.tableau import export_tableau

__all__ = ["export_tableau"]
