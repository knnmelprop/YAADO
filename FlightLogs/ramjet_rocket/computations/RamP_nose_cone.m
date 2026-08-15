clear all
close all

clc

%*********************data*************************%

nose_long=12;

rocket_wide=2; %diameter

x_resolution=.1;

k=0;

C=0.0;

%*********Von Karman y L-V Haack********%

%C = 0.333333 %for L-V Haack nose cones

%C = 0 %for Von Karman nose cones

for X = 0:x_resolution:nose_long

k = k + 1 ;

x=X/nose_long;

h=acos(1-2*x);

r(k)= sqrt((h-(1/2)*sin(2*h)+(C*((sin(h))^3)*h))/pi);

r(k)=r(k)*(rocket_wide*2);

end

%***********************************%

plot(r)