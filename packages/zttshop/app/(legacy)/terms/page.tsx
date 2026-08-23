import { redirect } from "next/navigation";

export default function LegacyTermsPage() {
  redirect("/en/terms");
}
