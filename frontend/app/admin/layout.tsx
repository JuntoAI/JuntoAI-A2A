import { cookies } from "next/headers";
import Link from "next/link";

const NAV_ITEMS = [
  { label: "Overview", href: "/admin" },
  { label: "Users", href: "/admin/users" },
  { label: "Simulations", href: "/admin/simulations" },
] as const;

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const cookieStore = await cookies();
  const adminSession = cookieStore.get("admin_session");

  // No session — render children directly (login page or middleware redirect)
  if (!adminSession?.value) {
    return <>{children}</>;
  }

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="flex w-56 flex-col bg-brand-charcoal text-white">
        <div className="px-5 py-6">
          <h1 className="text-lg font-semibold tracking-tight">
            JuntoAI Admin
          </h1>
        </div>
        <nav className="flex flex-col gap-1 px-3">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-md px-3 py-2 text-sm font-medium text-gray-300 transition-colors hover:bg-white/10 hover:text-white"
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>

      {/* Main content */}
      <main className="flex-1 bg-brand-offwhite p-8">{children}</main>
    </div>
  );
}
