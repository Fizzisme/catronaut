import { NextResponse } from "next/server";

export function ok() {
  return NextResponse.json({ ok: true });
}
