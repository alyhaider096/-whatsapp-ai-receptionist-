"""Dev-only helper: attach a WhatsApp test-number config and an LLM API key
to a tenant, until the dashboard (Week 3) can do this from the UI.

Sign up first (POST /auth/signup), then run:

  python scripts/seed_dev_tenant.py --email owner@example.com \\
      --waba-id 123456789 --phone-number-id 109876543210987 \\
      --whatsapp-token EAAxxxxxxxx --llm-key sk-xxxxxxxx \\
      --llm-model openai/gpt-4o-mini
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.core.security import encrypt_secret  # noqa: E402
from app.db.session import async_session_maker  # noqa: E402
from app.models.llm_config import LLMConfig  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.whatsapp_config import WhatsAppConfig  # noqa: E402


async def main(args: argparse.Namespace) -> None:
    async with async_session_maker() as db:
        user = await db.scalar(select(User).where(User.email == args.email))
        if user is None:
            raise SystemExit(
                f"No user for {args.email} -- sign up via POST /auth/signup first"
            )

        db.add(
            WhatsAppConfig(
                tenant_id=user.tenant_id,
                waba_id=args.waba_id,
                phone_number_id=args.phone_number_id,
                access_token_encrypted=encrypt_secret(args.whatsapp_token),
                status="connected",
            )
        )
        db.add(
            LLMConfig(
                tenant_id=user.tenant_id,
                provider="openai",
                model=args.llm_model,
                api_key_encrypted=encrypt_secret(args.llm_key),
            )
        )
        await db.commit()
        print(f"Seeded WhatsApp + LLM config for tenant_id={user.tenant_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--waba-id", required=True)
    parser.add_argument("--phone-number-id", required=True)
    parser.add_argument("--whatsapp-token", required=True)
    parser.add_argument("--llm-model", default="openai/gpt-4o-mini")
    parser.add_argument("--llm-key", required=True)
    asyncio.run(main(parser.parse_args()))
