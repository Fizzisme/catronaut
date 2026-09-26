"use server";

export async function subscribe(formData: FormData) {
  console.log("subscribed", formData.get("email"));
}
