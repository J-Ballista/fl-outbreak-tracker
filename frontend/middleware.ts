import { NextRequest, NextResponse } from "next/server";

const COOKIE_NAME = "fl_tracker_session";
const LOGIN_PATH = "/login";

// Routes that don't require auth
const PUBLIC_PATHS = new Set([LOGIN_PATH, "/api/login"]);

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  // Allow public paths and Next.js internals
  if (
    PUBLIC_PATHS.has(pathname) ||
    pathname.startsWith("/_next") ||
    pathname.startsWith("/favicon")
  ) {
    return NextResponse.next();
  }

  const session = req.cookies.get(COOKIE_NAME);

  if (!session?.value) {
    const loginUrl = req.nextUrl.clone();
    loginUrl.pathname = LOGIN_PATH;
    loginUrl.searchParams.set("from", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
