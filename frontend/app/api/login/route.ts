import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const DASHBOARD_PASSWORD = process.env.DASHBOARD_PASSWORD ?? "";
const COOKIE_NAME = "fl_tracker_session";
// 7 days
const MAX_AGE = 60 * 60 * 24 * 7;

export async function POST(req: NextRequest) {
  const { password } = await req.json();

  if (!DASHBOARD_PASSWORD) {
    // No password configured — always allow (dev mode)
    const res = NextResponse.json({ ok: true });
    (await cookies()).set(COOKIE_NAME, "dev", {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      maxAge: MAX_AGE,
      path: "/",
    });
    return res;
  }

  if (password !== DASHBOARD_PASSWORD) {
    return NextResponse.json({ error: "Wrong password" }, { status: 401 });
  }

  const cookieStore = await cookies();
  cookieStore.set(COOKIE_NAME, "authenticated", {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: MAX_AGE,
    path: "/",
  });

  return NextResponse.json({ ok: true });
}

export async function DELETE() {
  (await cookies()).delete(COOKIE_NAME);
  return NextResponse.json({ ok: true });
}
