// A destination marker is display metadata, separate from the routing code.
export function formatDestinationLabel(serviceLabel, destinationModifier) {
  return destinationModifier ? `${serviceLabel} ${destinationModifier}` : serviceLabel;
}
