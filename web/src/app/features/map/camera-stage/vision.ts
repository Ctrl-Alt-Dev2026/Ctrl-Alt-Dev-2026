// Presentation only. All inference, tracking and lighting rules live in Python.
export const VEHICLES = new Set(['car', 'truck', 'bus', 'tram', 'motorcycle', 'bicycle']);
export const LABEL_RO: Record<string, string> = {
  car: 'autoturism', truck: 'camion', bus: 'autobuz', tram: 'tramvai',
  motorcycle: 'motocicletă', bicycle: 'bicicletă', person: 'persoană',
};
