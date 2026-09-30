type Crumb = { label: string; href?: string };

export default function Breadcrumbs({ items }: { items: Crumb[] }) {
  return (
    <nav className="text-sm text-gray-500 mb-4" aria-label="เส้นทางนำทาง">
      <ol className="flex flex-wrap items-center gap-1">
        <li><a href="/" className="min-h-[32px] inline-flex items-center hover:text-blue-600 transition">หน้าแรก</a></li>
        {items.map((item, i) => (
          <li key={i} className="flex items-center gap-1">
            <span className="text-gray-300">/</span>
            {item.href ? (
              <a href={item.href} className="min-h-[32px] inline-flex items-center hover:text-blue-600 transition">{item.label}</a>
            ) : (
              <span className="text-gray-700 font-medium">{item.label}</span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
