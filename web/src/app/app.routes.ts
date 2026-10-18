import { Routes } from '@angular/router';

const mapPage = () => import('./features/map/map-page/map-page').then((m) => m.MapPage);

export const routes: Routes = [
  { path: '', loadComponent: mapPage, title: 'Harta priorităților' },
  { path: 'locatie/:id', loadComponent: mapPage, title: 'Fișa locației' },
  {
    path: 'fisa',
    loadComponent: () => import('./features/report/fisa-page/fisa-page').then((m) => m.FisaPage),
    title: 'Fișa de verificare',
  },
  { path: '**', redirectTo: '' },
];
