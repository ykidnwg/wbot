import { NextRequest, NextResponse } from "next/server";

type RouteContext = { params: Promise<{ path: string[] }> };

export const dynamic = "force-dynamic";

async function proxy(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  const { path } = await context.params;
  const backendOrigin = process.env.BACKEND_INTERNAL_URL ?? "http://backend:8000";
  const target = new URL(`/api/v1/${path.map(encodeURIComponent).join("/")}`, backendOrigin);
  target.search = request.nextUrl.search;

  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  const cookie = request.headers.get("cookie");
  if (contentType) headers.set("content-type", contentType);
  if (cookie) headers.set("cookie", cookie);

  const method = request.method;
  const body = method === "GET" || method === "HEAD" ? undefined : await request.arrayBuffer();
  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method,
      headers,
      body,
      cache: "no-store",
      redirect: "manual",
    });
  } catch (error: unknown) {
    if (error instanceof TypeError) {
      return NextResponse.json({ detail: "Backend unavailable" }, { status: 502 });
    }
    throw error;
  }

  const responseHeaders = new Headers();
  const upstreamContentType = upstream.headers.get("content-type");
  const setCookie = upstream.headers.get("set-cookie");
  const location = upstream.headers.get("location");
  if (upstreamContentType) responseHeaders.set("content-type", upstreamContentType);
  if (setCookie) responseHeaders.set("set-cookie", setCookie);
  if (location) responseHeaders.set("location", location);

  const responseBody = upstream.status === 204 || upstream.status === 304 ? null : upstream.body;
  return new NextResponse(responseBody, { status: upstream.status, headers: responseHeaders });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
