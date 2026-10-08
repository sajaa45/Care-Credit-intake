const euroFormat = new Intl.NumberFormat("nl-NL", { style: "currency", currency: "EUR" });

export const euro = (amount) => euroFormat.format(Number(amount));

export const dateTime = (iso) => new Date(iso).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });

export const STATUS_LABELS = {
  submitted: "Submitted",
  accept: "Accepted",
  refer: "To review",
  decline: "Declined",
};

export const HOUSEHOLD_LABELS = {
  single: "Single",
  single_with_children: "Single with children",
  couple: "Couple",
  couple_with_children: "Couple with children",
};
