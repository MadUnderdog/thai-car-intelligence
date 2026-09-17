type Crumb = { label: string; href?: string };

export default function Breadcrumbs({ items }: { items: Crumb[] }) {
  return (
    <nav className="text-sm text-gray-500 mb-4" aria-label="面包屑导航">
      <ol className="flex flex-wrap items-center gap-1">
        <li><a href="/" className="hover:text-blue-600 transition">หน้าแรก</a></li>
        {items.map((item, i) => (
          <li key={i} className="flex items-center gap-1">
            <span className="text-gray-300">/</span>
            {item.href ? (
              <a href={item.href} className="hover:text-blue-600 transition">{item.label}</a>
            ) : (
              <span className="text-gray-700 font-medium">{item.label}</span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
