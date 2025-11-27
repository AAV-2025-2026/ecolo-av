a = 80;%Tie Rod Length
w = 530;%control arm
s = 570;%static arm
u = 55;
l = 1570;

linMot_default = 500;
abstract = 450;

stock_linmot = acos(((a^2)+(abstract^2)-(linMot_default^2))/(2*a*abstract));


linMot_extendo = 520;
currentAngle = acos(((a^2)+(abstract^2)-(linMot_extendo^2))/(2*a*abstract))-stock_linmot;


stockAngle = asin((s-w)/(2*a));
%convergencePoint = tan(stockAngle)*(w/2);

T = 770;%Track width
L = l;%Wheelbase

phi1_deg = 0;
phi2_deg = rad2deg(currentAngle);


%phi1 = deg2rad(phi1_deg);
phi2 = deg2rad(phi2_deg);%Steering angle of the passenger wheel ## + means turning right, - means turning left

x = (a/s)*sin(stockAngle);
y = (a/s)*cos(stockAngle);

%A = 1-cos(phi1-phi2);
%B = 2-cos(phi1)-cos(phi2);
%C = sin(phi2) - sin(phi1);
%D = 2* sin(phi1-phi2);

f = @(phi1) (1 - cos(phi1 - phi2))*(x^2 - y^2) ...
           + (2 - cos(phi1) - cos(phi2))*x ...
           + (sin(phi2) - sin(phi1))*y ...
           + 2*sin(phi1 - phi2)*x*y;

phi1 = fzero(f, 0);
phi1_deg = rad2deg(phi1);


R1 = L/tan(phi1) - T/2;
R2 = L/tan(phi2) + T/2;


fprintf("R1 radius(mm): %f \n", R1);
fprintf("R2 radius(mm): %f \n", R2);

%Freudenstein equation
%a1 = s;
%a2 = a;
%a4 = a;
%a3 = w;
%beta = asin((a1-a3)/(2*a2));
%k1 = ((a1^2)+(a2^2)-(a3^2)+(a4^2))/(2*a2*a4);
%k2 = a1/a2;
%k3 = a1/a4;
%
%sigma2 = (pi/2) + (beta-phi2);
%
%f = @(sigma1) k1+k2*cos(sigma2)-k3*cos(sigma1)-cos(sigma1-sigma2);
%sigma1 = fzero(f,0);
%phi1_2 = rad2deg((pi/2)-sigma1-beta);



%inner_deg = 35;
%inner = deg2rad(inner_deg);
%f = @(outer) (T - a*(sin(inner) + sin(outer)))^2 + (a*(cos(inner) - cos(outer)))^2 - s^2;
%outer_guess = deg2rad(inner_deg - 10);
%outer = fzero(f, outer_guess);
%outer_deg = rad2deg(outer);



%R = ((tan(inner)/L)^-1) + T/2;
%R2 = ((tan(outer)/L)^-1) - T/2;


%f2 = @(outer)  ;