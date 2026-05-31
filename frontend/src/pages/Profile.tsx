import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { IconGear, IconImport, IconInfo, IconChevron } from "../ui/icons";

export default function Profile() {
  const nav = useNavigate();
  const [count, setCount] = useState<number | null>(null);

  useEffect(() => {
    api.listBatches().then((b) => setCount(b.length)).catch(() => setCount(null));
  }, []);

  const row = (
    Icon: (p: { size?: number }) => JSX.Element,
    title: string,
    sub: string,
    to: string
  ) => (
    <button className="menu-row" onClick={() => nav(to)}>
      <span className="menu-ico"><Icon size={19} /></span>
      <div className="menu-body">
        <div className="menu-title">{title}</div>
        <div className="menu-sub">{sub}</div>
      </div>
      <span className="menu-chevron"><IconChevron /></span>
    </button>
  );

  return (
    <div className="screen">
      <div className="screen-head" style={{ textAlign: "center" }}>
        <div className="avatar" style={{ margin: "0 auto 14px" }}>AV</div>
        <h1 style={{ marginBottom: 2 }}>Alexey</h1>
        <p className="muted small">
          {count == null ? "—" : `${count} pattern set${count === 1 ? "" : "s"} in your library`}
        </p>
      </div>

      <div className="menu">
        {row(IconGear, "Voice & playback", "Voices, speed, pauses, default order", "/settings")}
        {row(IconImport, "Import a batch", "Paste patterns from a draft", "/import")}
        {row(IconInfo, "About", "English Executive — a private practice library", "/profile")}
      </div>
    </div>
  );
}
