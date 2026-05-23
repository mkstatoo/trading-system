from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/trading", tags=["trading"])


class OrderRequest(BaseModel):
    market: str = Field(..., examples=["BTCUSDT"])
    side: str = Field(..., pattern="^(buy|sell)$")
    amount: float = Field(..., gt=0)
    price: float = Field(..., gt=0)


@router.get("/positions")
async def get_positions():
    from app.main import portfolio, paper_exchange

    return {
        "portfolio_positions": portfolio.positions,
        "paper_positions": paper_exchange.positions,
        "open_trades": portfolio.open_trades,
    }


@router.get("/history")
async def order_history():
    from app.main import paper_exchange

    return {"orders": paper_exchange.order_history[-50:]}


@router.post("/order")
async def manual_order(req: OrderRequest):
    from app.main import paper_exchange, portfolio, executor

    if req.side not in ("buy", "sell"):
        raise HTTPException(status_code=400, detail="side must be buy or sell")

    if req.side == "buy":
        signal = {
            "symbol": req.market.upper(),
            "price": req.price,
            "amount": req.amount,
            "side": "buy",
        }
        result = await executor.execute(portfolio, signal)
    else:
        result = await paper_exchange.place_order(
            market=req.market.upper(),
            side="sell",
            amount=req.amount,
            price=req.price,
        )
        if result.get("status") == "filled":
            portfolio.close_position(req.market.upper())

    if not result or result.get("code") == 1:
        raise HTTPException(status_code=400, detail=result)
    return result
