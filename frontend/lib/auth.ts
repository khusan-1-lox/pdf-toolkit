import type { NextAuthOptions } from "next-auth";
import GoogleProvider from "next-auth/providers/google";

const clientId = process.env.GOOGLE_CLIENT_ID || "dummy";
const clientSecret = process.env.GOOGLE_CLIENT_SECRET || "dummy";

export const authOptions: NextAuthOptions = {
  providers: [
    GoogleProvider({
      clientId,
      clientSecret,
    }),
  ],
  callbacks: {
    async signIn({ user }) {
      const allowed = process.env.ALLOWED_EMAILS;
      if (!allowed || allowed.trim() === "") return true;
      const list = allowed
        .split(",")
        .map((s) => s.trim().toLowerCase())
        .filter(Boolean);
      if (list.length === 0) return true;
      return list.includes((user.email || "").toLowerCase());
    },
  },
};
