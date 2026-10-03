def can_refund(
    paid: bool,
    days_since_purchase: int,
) -> bool:
    """Refunds require payment and <= 30 days."""
    return (
        paid
        and days_since_purchase <= 30
    )
