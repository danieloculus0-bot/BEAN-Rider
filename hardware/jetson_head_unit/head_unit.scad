// BEAN-Rider 10-inch Jetson head unit; printable fit-check ONLY, dimensions mm.
// -D 'part="jetson_tray"' (or screen_tab, cable_anchor) to select part.
// Not crash rated; no assumed Jetson board-hole dimensions.
part="jetson_tray";
$fn=48;
plate_w=160; plate_h=126; plate_t=5; corner_r=7;
slot_d=3.4; screen_tab_len=60; screen_tab_w=22; screen_tab_t=5; screen_lip_h=8;
module rounded_plate(w,h,r) {
  hull() for(x=[-w/2+r,w/2-r],y=[-h/2+r,h/2-r]) translate([x,y]) circle(r=r);
}
module slot_x(length,diameter,depth) {
  hull() for(x=[-length/2+diameter/2,length/2-diameter/2])
    translate([x,0,0]) cylinder(d=diameter,h=depth);
}
module jetson_tray() {
  difference() {
    linear_extrude(height=plate_t) rounded_plate(plate_w,plate_h,corner_r);
    // Generic M3/cable-tie slots, NOT Jetson hole coordinates.
    for(y=[-43,43],x=[-47,47]) translate([x,y,-1]) slot_x(23,slot_d,plate_t+2);
    for(y=[-27,-9,9,27],x=[-32,32]) translate([x,y,-1]) slot_x(28,7,plate_t+2);
    for(y=[-38,38],x=[-69,69]) translate([x,y,-1]) slot_x(10,4.4,plate_t+2);
  }
}
module screen_tab() {
  difference() {
    union() {
      translate([0,0,screen_tab_t/2])
        cube([screen_tab_len,screen_tab_w,screen_tab_t],center=true);
      // Alignment lip for enclosed display housing ONLY, NOT bare glass.
      translate([-screen_tab_len/2+5,-screen_tab_w/2+2,screen_tab_t+screen_lip_h/2])
        cube([10,4,screen_lip_h],center=true);
    }
    translate([9,0,-1]) slot_x(23,slot_d,screen_tab_t+2);
    translate([-16,0,-1]) cylinder(d=slot_d,h=screen_tab_t+2);
  }
}
module cable_anchor() {
  difference() {
    translate([0,0,2.5]) cube([34,22,5],center=true);
    for(x=[-11,11]) translate([x,0,-1]) cylinder(d=3.4,h=7);
    for(y=[-7,7]) translate([0,y,-1]) cube([12,3,7],center=true);
  }
}
if(part=="jetson_tray") jetson_tray();
else if(part=="screen_tab") screen_tab();
else if(part=="cable_anchor") cable_anchor();
else assert(false,str("unknown part: ",part));
