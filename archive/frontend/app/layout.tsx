import type {Metadata} from "next";
import "./globals.css";
import "./product.css";
export const metadata:Metadata={title:"Venv | بيئة عمل افتراضية",description:"تدرّب على وظيفتك الأولى مع فريق AI"};
export default function Layout({children}:{children:React.ReactNode}){return <html lang="ar" dir="rtl"><body><div className="noise"/>{children}</body></html>}
